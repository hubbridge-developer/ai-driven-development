from django.contrib import admin
from src.add_api.models import Namespace, WorkflowRun, GeneratedSpec, SpecRepoConfig, Repository


@admin.register(Namespace)
class NamespaceAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "next_spec_sequence", "created_at"]


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = ["workflow_id", "status", "current_agent", "created_at", "updated_at"]
    list_filter = ["status"]


@admin.register(GeneratedSpec)
class GeneratedSpecAdmin(admin.ModelAdmin):
    list_display = ["spec_id", "namespace", "version", "indexed_at", "created_at"]


@admin.register(SpecRepoConfig)
class SpecRepoConfigAdmin(admin.ModelAdmin):
    list_display = ["spec_repo_url", "branch", "active", "created_at"]


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ["repo_slug", "namespace", "created_at"]
