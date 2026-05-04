"""
Starian — Configuracao Django para o servidor MCP.

As credenciais do Supabase sao fornecidas via variaveis de ambiente.
Utilize um arquivo ``.env`` na raiz do projeto (carregado automaticamente
se ``python-dotenv`` estiver instalado).
"""

from __future__ import annotations

import os
from pathlib import Path

# ───────────────────────────────────────────────
# Paths
# ───────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Carrega .env automaticamente se disponivel
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# ───────────────────────────────────────────────
# Core
# ───────────────────────────────────────────────
SECRET_KEY: str = os.getenv(
    "DJANGO_SECRET_KEY",
    "starian-dev-key-change-in-production",
)

DEBUG: bool = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1")

ALLOWED_HOSTS: list[str] = ["*"]

# ───────────────────────────────────────────────
# Apps instalados
# ───────────────────────────────────────────────
INSTALLED_APPS: list[str] = [
    "django.contrib.contenttypes",
    "starian",
]

# ───────────────────────────────────────────────
# Banco de Dados — PostgreSQL no Supabase
# ───────────────────────────────────────────────
DATABASES: dict = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("SUPABASE_DB_NAME", "postgres"),
        "USER": os.getenv("SUPABASE_DB_USER", "postgres"),
        "PASSWORD": os.getenv("SUPABASE_DB_PASSWORD", ""),
        "HOST": os.getenv("SUPABASE_DB_HOST", "localhost"),
        "PORT": os.getenv("SUPABASE_DB_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
    },
}

# ───────────────────────────────────────────────
# Internacionalizacao
# ───────────────────────────────────────────────
LANGUAGE_CODE: str = "pt-br"
TIME_ZONE: str = "America/Sao_Paulo"
USE_I18N: bool = True
USE_TZ: bool = True

# ───────────────────────────────────────────────
# Chave primaria padrao
# ───────────────────────────────────────────────
DEFAULT_AUTO_FIELD: str = "django.db.models.AutoField"
