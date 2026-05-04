"""
Starian MCP Server - Revisor Autonomo de Merge Requests (Squad 07).

Servidor MCP (Model Context Protocol) com transporte **stdio** que expoe:

* **Resource** ``starian://projects/{project_id}/business-rules``
  -> Regras de negocio ativas de um projeto.
* **Tool** ``analyze_mr_diff``
  -> Analise de diff via LangChain (ChatOpenAI) com scoring 0-100.

Guardrails:
  - Timeout de 30 s na chamada ao LLM (``asyncio.wait_for``).
  - Fallback com score neutro (50) em caso de qualquer falha.
  - Diff vazio -> aprovacao automatica (score 100).
  - Score <= 50 -> ``critical_alert: true``.
  - Nenhum codigo-fonte e gravado em disco.

Execucao::

    python starian/server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# -----------------------------------------------
# Django bootstrap - DEVE ocorrer ANTES de qualquer import de models
# -----------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

# Imports pos-bootstrap ------------------------------------------------
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

from starian.mcp_db_service import (  # noqa: E402
    get_project_rules_async,
    save_analysis_history_async,
)

# -----------------------------------------------
# Constantes
# -----------------------------------------------
ANALYSIS_TIMEOUT_SECONDS: int = 30
NEUTRAL_SCORE: int = 50
AUTO_APPROVE_SCORE: int = 100
CRITICAL_THRESHOLD: int = 50

SERVER_NAME: str = "Starian-MR-Analyzer"
SERVER_VERSION: str = "1.0.0"

FALLBACK_FEEDBACK: str = (
    "Erro na analise automatica. Revisao manual obrigatoria."
)
EMPTY_DIFF_FEEDBACK: str = "Nenhuma alteracao detectada."

# -----------------------------------------------
# Logging  (stderr - stdout e reservado ao transporte stdio)
# -----------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("starian.server")

# -----------------------------------------------
# FastMCP Server
# -----------------------------------------------
mcp = FastMCP(name=SERVER_NAME)

# -----------------------------------------------
# LangChain - Prompt estruturado
# -----------------------------------------------
_SYSTEM_PROMPT: str = """\
Voce e um revisor de codigo senior. Analise o diff de um Merge Request \
com base nas regras de negocio fornecidas.

Regras de Negocio do Projeto:
{business_rules}

Instrucoes:
1. Avalie cada alteracao do diff contra as regras acima.
2. Atribua um score de 0 (reprovado total) a 100 (aprovado total).
3. Gere um feedback tecnico detalhado justificando o score.

Retorne EXCLUSIVAMENTE um JSON valido com esta estrutura \
(sem markdown, sem texto extra):
{{"score": <int 0-100>, "feedback": "<string>"}}\
"""

_HUMAN_PROMPT: str = """\
Diff do Merge Request:
```
{diff_content}
```\
"""

_analysis_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human", _HUMAN_PROMPT),
])


def _build_llm() -> ChatOpenAI:
    """Instancia o ChatModel da OpenAI.

    Le ``OPENAI_API_KEY`` e opcionalmente ``OPENAI_MODEL`` do ambiente.
    """
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        max_tokens=1024,
    )


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Extrai o JSON da resposta do LLM de forma resiliente.

    Tenta localizar o primeiro ``{`` e o ultimo ``}`` para lidar
    com respostas que contenham texto extra ao redor do JSON.
    """
    text = raw.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"JSON nao encontrado na resposta do LLM: {text!r}")

    return json.loads(text[start : end + 1])


def _build_result(
    score: int,
    feedback: str,
    project_id: int,
    mr_external_id: int,
    author_name: str,
) -> dict[str, Any]:
    """Monta o payload de retorno da Tool MCP.

    Adiciona ``critical_alert: true`` quando ``score <= 50``.
    """
    result: dict[str, Any] = {
        "score": score,
        "feedback": feedback,
        "project_id": project_id,
        "mr_external_id": mr_external_id,
        "author_name": author_name,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }

    if score <= CRITICAL_THRESHOLD:
        result["critical_alert"] = True

    return result


# -----------------------------------------------
# Resource - Regras de Negocio
# -----------------------------------------------

@mcp.resource("starian://projects/{project_id}/business-rules")
async def get_project_business_rules(project_id: int) -> str:
    """Retorna as Business Rules ativas de um projeto especifico.

    Realiza JOIN entre ``project_business_rules`` e ``business_rules``
    e devolve as descricoes ordenadas por nivel de risco (decrescente).
    """
    logger.info("Resource solicitado: regras do projeto %d", project_id)
    return await get_project_rules_async(project_id)


# -----------------------------------------------
# Tool - Analise de Merge Request
# -----------------------------------------------

@mcp.tool()
async def analyze_mr_diff(
    diff_content: str,
    project_id: int,
    mr_external_id: int,
    author_name: str,
) -> str:
    """Analisa o diff de um Merge Request e retorna score + feedback.

    Parametros:
      - diff_content: Conteudo do diff do Merge Request.
      - project_id: ID do projeto no banco de dados.
      - mr_external_id: ID externo do MR no GitHub/GitLab.
      - author_name: Nome do autor do Merge Request.

    Retorna um JSON com score (0-100), feedback e, se score <= 50,
    uma flag ``critical_alert: true``.
    """
    logger.info(
        "Tool chamada: analyze_mr_diff | MR#%d | Projeto %d | Autor: %s",
        mr_external_id,
        project_id,
        author_name,
    )

    # -- Diff vazio -> aprovacao automatica -------------------------
    if not diff_content or not diff_content.strip():
        logger.info("Diff vazio detectado - aprovacao automatica.")
        result = _build_result(
            score=AUTO_APPROVE_SCORE,
            feedback=EMPTY_DIFF_FEEDBACK,
            project_id=project_id,
            mr_external_id=mr_external_id,
            author_name=author_name,
        )
        await _safe_save_history(
            project_id, mr_external_id, AUTO_APPROVE_SCORE,
            author_name, EMPTY_DIFF_FEEDBACK,
        )
        return json.dumps(result, ensure_ascii=False)

    # -- Analise com LangChain (com timeout e fallback) ------------
    try:
        score, feedback = await asyncio.wait_for(
            _invoke_llm_analysis(diff_content, project_id),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Timeout (%ds) na analise do MR#%d.",
            ANALYSIS_TIMEOUT_SECONDS,
            mr_external_id,
        )
        score, feedback = NEUTRAL_SCORE, FALLBACK_FEEDBACK
    except Exception:
        logger.exception(
            "Erro inesperado na analise do MR#%d.", mr_external_id,
        )
        score, feedback = NEUTRAL_SCORE, FALLBACK_FEEDBACK

    # -- Persistir resultado ---------------------------------------
    await _safe_save_history(
        project_id, mr_external_id, score, author_name, feedback,
    )

    result = _build_result(
        score=score,
        feedback=feedback,
        project_id=project_id,
        mr_external_id=mr_external_id,
        author_name=author_name,
    )

    logger.info(
        "Analise concluida: MR#%d | Score %d | Alerta critico: %s",
        mr_external_id,
        score,
        score <= CRITICAL_THRESHOLD,
    )

    return json.dumps(result, ensure_ascii=False)


# -----------------------------------------------
# Funcoes auxiliares internas
# -----------------------------------------------

async def _invoke_llm_analysis(
    diff_content: str,
    project_id: int,
) -> tuple[int, str]:
    """Executa a chain LangChain e devolve ``(score, feedback)``.

    Raises
    ------
    ValueError
        Se a resposta do LLM nao contiver JSON valido ou score fora do range.
    Exception
        Qualquer erro de rede/API e propagado para o caller tratar.
    """
    # 1. Buscar regras de negocio do projeto
    business_rules = await get_project_rules_async(project_id)

    # 2. Montar a chain
    llm = _build_llm()
    chain = _analysis_prompt | llm

    # 3. Invocar o LLM  (ainvoke e nativo async no LangChain)
    response = await chain.ainvoke({
        "business_rules": business_rules,
        "diff_content": diff_content,
    })

    # 4. Parse da resposta
    parsed = _parse_llm_response(response.content)

    score = int(parsed.get("score", NEUTRAL_SCORE))
    feedback = str(parsed.get("feedback", FALLBACK_FEEDBACK))

    # 5. Clamp do score para o intervalo valido
    score = max(0, min(100, score))

    return score, feedback


async def _safe_save_history(
    project_id: int,
    mr_external_id: int,
    score: int,
    author_name: str,
    ai_feedback: str,
) -> None:
    """Salva no historico sem jamais propagar excecoes ao caller.

    Se a persistencia falhar, o erro e logado mas o servidor
    continua operando normalmente.
    """
    try:
        await save_analysis_history_async(
            project_id=project_id,
            mr_external_id=mr_external_id,
            score=score,
            author_name=author_name,
            ai_feedback=ai_feedback,
        )
    except Exception:
        logger.exception(
            "Falha ao salvar historico para MR#%d (projeto %d). "
            "O resultado foi retornado ao cliente, mas nao persistido.",
            mr_external_id,
            project_id,
        )


# -----------------------------------------------
# Inicializacao
# -----------------------------------------------

def main() -> None:
    """Entry-point do servidor MCP via transporte stdio."""
    logger.info(
        "%s v%s iniciando (transporte: stdio)...",
        SERVER_NAME,
        SERVER_VERSION,
    )
    mcp.run()


if __name__ == "__main__":
    main()
