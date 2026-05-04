"""
Starian - Mapeamento ORM Django para o banco PostgreSQL (Supabase).

Cada model utiliza ``managed = False`` e ``db_table`` para mapear
exatamente as tabelas ja existentes no Supabase, sem que o Django
tente criar ou alterar o schema.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# -----------------------------------------------
#  managers
# -----------------------------------------------

class Manager(models.Model):
    """Gestor responsavel por um ou mais projetos."""

    manager_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, max_length=255)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "managers"
        managed = False
        verbose_name = "Manager"
        verbose_name_plural = "Managers"

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


# -----------------------------------------------
#  project
# -----------------------------------------------

class Project(models.Model):
    """Projeto Git vinculado a um gestor."""

    project_id = models.AutoField(primary_key=True)
    manager = models.ForeignKey(
        Manager,
        on_delete=models.CASCADE,
        db_column="manager_id",
        related_name="projects",
    )
    git_id = models.CharField(unique=True, max_length=255)
    full_name = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "project"
        managed = False
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self) -> str:
        return self.full_name


# -----------------------------------------------
#  business_rules
# -----------------------------------------------

class BusinessRule(models.Model):
    """Regra de negocio para avaliacao de codigo."""

    rule_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    risk_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Nivel de risco: 1 (baixo) a 100 (critico).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "business_rules"
        managed = False
        verbose_name = "Business Rule"
        verbose_name_plural = "Business Rules"

    def __str__(self) -> str:
        return f"[Risco {self.risk_level}] {self.name}"


# -----------------------------------------------
#  project_business_rules  (tabela associativa)
# -----------------------------------------------

class ProjectBusinessRule(models.Model):
    """Associacao N:N entre Projeto e Regra de Negocio."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="project_rules",
    )
    rule = models.ForeignKey(
        BusinessRule,
        on_delete=models.CASCADE,
        db_column="rule_id",
        related_name="rule_projects",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "project_business_rules"
        managed = False
        unique_together = (("project", "rule"),)
        verbose_name = "Project Business Rule"
        verbose_name_plural = "Project Business Rules"

    def __str__(self) -> str:
        return f"{self.project} - {self.rule}"


# -----------------------------------------------
#  analysis_history
# -----------------------------------------------

class AnalysisHistory(models.Model):
    """Historico de analises de Merge Requests."""

    analysis_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="analyses",
    )
    mr_external_id = models.IntegerField(
        help_text="ID externo do Merge Request no GitHub/GitLab.",
    )
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Nota de 0 (reprovado) a 100 (aprovado).",
    )
    author_name = models.CharField(max_length=255)
    ai_feedback = models.TextField()
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analysis_history"
        managed = False
        verbose_name = "Analysis History"
        verbose_name_plural = "Analysis Histories"

    def __str__(self) -> str:
        return f"MR#{self.mr_external_id} - Score {self.score}"


# -----------------------------------------------
#  webhook_logs
# -----------------------------------------------

class WebhookLog(models.Model):
    """Registro de auditoria de webhooks recebidos."""

    log_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="webhook_logs",
    )
    payload = models.JSONField(
        help_text="Payload bruto do webhook (GitHub/GitLab).",
    )
    status_code = models.IntegerField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_logs"
        managed = False
        verbose_name = "Webhook Log"
        verbose_name_plural = "Webhook Logs"

    def __str__(self) -> str:
        return f"Log #{self.log_id} - Project {self.project_id}"
