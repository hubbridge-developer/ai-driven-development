from django.urls import path, include
from rest_framework.routers import DefaultRouter
from src.aidd_api import views

router = DefaultRouter()
router.register(r"namespaces", views.NamespaceViewSet, basename="namespace")

urlpatterns = [
    # Workflow endpoints
    path("workflow/start", views.workflow_start, name="workflow-start"),
    path("workflow/<str:workflow_id>", views.workflow_detail, name="workflow-detail"),
    path("workflow/<str:workflow_id>/approve", views.workflow_approve, name="workflow-approve"),
    path("workflow/<str:workflow_id>/reject", views.workflow_reject, name="workflow-reject"),
    path("workflow/<str:workflow_id>/cancel", views.workflow_cancel, name="workflow-cancel"),
    path("workflow/<str:workflow_id>/spec", views.workflow_spec, name="workflow-spec"),
    path("workflow/<str:workflow_id>/code", views.workflow_code, name="workflow-code"),
    path("workflow/<str:workflow_id>/approve-code", views.workflow_code_approve, name="workflow-code-approve"),
    path("workflow/<str:workflow_id>/reject-code", views.workflow_code_reject, name="workflow-code-reject"),
    path("workflows", views.workflow_list, name="workflow-list"),
    # Specs
    path("specs", views.spec_list, name="spec-list"),
    path("specs/search", views.spec_search, name="spec-search"),
    # Namespaces (router)
    path("", include(router.urls)),
]
