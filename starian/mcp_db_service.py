"""
Starian - Camada de abstracao assincrona para o servidor MCP.

Todas as funcoes utilizam ``sync_to_async`` do **asgiref** para
encapsular consultas sincronas do Django ORM em coroutines
compativeis com o event-loop do servidor MCP.

Nenhum dado e gravado em disco fora do banco de dados; todo
processamento ocorre em memoria.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError

from starian.models import (
    AnalysisHistory,
    BusinessRule,
    Project,
    WebhookLog,
)

logger = logging.getLogger("starian.db_service")


# -----------------------------------------------
#  Leitura de Regras de Negocio
# -----------------------------------------------

@sync_to_async
def _fetch_project_rules(project_id: int) -> str:
    """Busca sincrona das regras - executada em thread-pool pelo asgiref.

    Faz o JOIN implicito entre ``project_business_rules`` e
    ``business_rules`` utilizando o related_name ``rule_projects``
    definido no model ``ProjectBusinessRule``.

    Retorna uma string concatenada com as descricoes de todas as
    regras ativas do projeto, ordenadas por ``risk_level`` decrescente.
    """
    rules = (
        BusinessRule.objects
        .filter(
            rule_projects__project_id=project_id,
            rule_projects__is_active=True,
            is_active=True,
        )
        .order_by("-risk_level")
        .values("name", "description", "risk_level")
    )

    if not rules.exists():
        return "Nenhuma regra de negocio ativa encontrada para este projeto."

    lines: list[str] = []
    for rule in rules:
        lines.append(
            f"[Risco {rule['risk_level']}] {rule['name']}: {rule['description']}"
        )
    return "\n".join(lines)


async def get_project_rules_async(project_id: int) -> str:
    """Retorna as descricoes das regras ativas do projeto.

    Realiza JOIN entre ``project_business_rules`` e ``business_rules``
    e devolve uma string combinada pronta para ser injetada no prompt
    do LLM.
    """
    return await _fetch_project_rules(project_id)


# -----------------------------------------------
#  Persistencia - Historico de Analises
# -----------------------------------------------

@sync_to_async
def _save_analysis(
    project_id: int,
    mr_external_id: int,
    score: int,
    author_name: str,
    ai_feedback: str,
) -> AnalysisHistory:
    """Cria registro sincrono no historico de analises.

    Valida o range do score (0-100) antes de persistir.
    Levanta ``ValidationError`` caso o valor esteja fora do intervalo.
    """
    if not (0 <= score <= 100):
        raise ValidationError(
            f"Score {score} fora do intervalo permitido (0-100)."
        )

    project = Project.objects.get(project_id=project_id)

    record = AnalysisHistory(
        project=project,
        mr_external_id=mr_external_id,
        score=score,
        author_name=author_name,
        ai_feedback=ai_feedback,
    )
    record.full_clean()
    record.save()

    logger.info(
        "Analise salva: MR#%d | Score %d | Projeto %d",
        mr_external_id,
        score,
        project_id,
    )
    return record


async def save_analysis_history_async(
    project_id: int,
    mr_external_id: int,
    score: int,
    author_name: str,
    ai_feedback: str,
) -> None:
    """Salva o resultado da analise validando o range do score (0-100).

    Parameters
    ----------
    project_id:
        Chave primaria do projeto no banco.
    mr_external_id:
        ID externo do Merge Request (GitHub/GitLab).
    score:
        Nota de 0 a 100 atribuida pela analise.
    author_name:
        Nome do autor do Merge Request.
    ai_feedback:
        Texto de feedback gerado pela IA.
    """
    await _save_analysis(
        project_id, mr_external_id, score, author_name, ai_feedback,
    )


# -----------------------------------------------
#  Persistencia - Auditoria de Webhooks
# -----------------------------------------------

@sync_to_async
def _save_webhook(
    project_id: int,
    payload: dict[str, Any],
    status_code: int,
) -> WebhookLog:
    """Cria registro sincrono de auditoria de webhook."""
    project = Project.objects.get(project_id=project_id)

    record = WebhookLog(
        project=project,
        payload=payload,
        status_code=status_code,
    )
    record.save()

    logger.info(
        "Webhook log salvo: Projeto %d | Status %d",
        project_id,
        status_code,
    )
    return record


async def save_webhook_log_async(
    project_id: int,
    payload: dict[str, Any],
    status_code: int,
) -> None:
    """Salva a auditoria do webhook recebido.

    Parameters
    ----------
    project_id:
        Chave primaria do projeto no banco.
    payload:
        Corpo bruto do webhook (dicionario JSON).
    status_code:
        Codigo HTTP de status do webhook.
    """
    await _save_webhook(project_id, payload, status_code)
