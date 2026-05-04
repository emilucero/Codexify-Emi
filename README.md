# Starian MCP Server - Analisador de Merge Requests

> Servidor MCP (Model Context Protocol) para a **Squad 07** que atua como revisor autonomo de codigo em Merge Requests, utilizando **LangChain** + **ChatOpenAI** e persistencia no **PostgreSQL (Supabase)** via **Django ORM**.

## Estrutura do Projeto

```
codexify/
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
├── manage.py
├── config/
│   ├── __init__.py
│   └── settings.py          # Django settings (env vars do Supabase)
└── starian/
    ├── __init__.py
    ├── apps.py               # Django AppConfig
    ├── models.py             # 6 models mapeando tabelas do Supabase
    ├── mcp_db_service.py     # Camada async (sync_to_async)
    └── server.py             # FastMCP server + LangChain
```

## Pre-requisitos

- Python 3.11+
- Banco PostgreSQL no Supabase (tabelas ja criadas)
- Chave de API da OpenAI

## Instalacao

```bash
# 1. Clone o repositorio
git clone <url-do-repo>
cd codexify

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instale as dependencias
pip install -r requirements.txt

# 4. Configure as variaveis de ambiente
copy .env.example .env
# Edite o .env com suas credenciais
```

## Configuracao

Edite o arquivo `.env` com suas credenciais:

```env
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=sua-senha
SUPABASE_DB_HOST=db.xxxxxxxxxxx.supabase.co
SUPABASE_DB_PORT=5432

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Execucao

```bash
python starian/server.py
```

O servidor inicia no transporte **stdio** (compativel com Claude Desktop, Cursor, etc.).

## Tools & Resources expostos

| Tipo     | URI / Nome                                          | Descricao                                    |
|----------|-----------------------------------------------------|----------------------------------------------|
| Resource | `starian://projects/{project_id}/business-rules`    | Regras de negocio ativas do projeto          |
| Tool     | `analyze_mr_diff`                                   | Analisa diff do MR e retorna score + feedback|

### Parametros de `analyze_mr_diff`

| Parametro        | Tipo  | Descricao                           |
|------------------|-------|-------------------------------------|
| `diff_content`   | `str` | Conteudo do diff do Merge Request   |
| `project_id`     | `int` | ID do projeto no banco              |
| `mr_external_id` | `int` | ID externo do MR (GitHub/GitLab)    |
| `author_name`    | `str` | Nome do autor do MR                 |

### Retorno JSON

```json
{
  "score": 72,
  "feedback": "O codigo segue as regras de seguranca...",
  "project_id": 1,
  "mr_external_id": 42,
  "author_name": "dev-maria",
  "analyzed_at": "2026-05-03T23:00:00+00:00"
}
```

Se `score <= 50`, o retorno inclui `"critical_alert": true`.

## Guardrails

- **Timeout 30s**: se o LLM nao responder, retorna score neutro (50).
- **Fallback**: qualquer erro -> score 50 + "Revisao manual obrigatoria."
- **Diff vazio**: aprovacao automatica (score 100).
- **Seguranca**: nenhum codigo-fonte e gravado em disco.

## Teste com MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector python starian/server.py
```

## Squad 07 - Starian
