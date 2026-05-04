"""Starian — Configuracao do Django App."""

from django.apps import AppConfig


class StarianConfig(AppConfig):
    """Configuracao do app Starian para o Django."""

    name: str = "starian"
    default_auto_field: str = "django.db.models.AutoField"
    verbose_name: str = "Starian - MR Analyzer"
