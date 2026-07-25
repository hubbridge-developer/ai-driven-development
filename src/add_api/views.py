"""REST API views for ADD workflow management."""

import uuid
import threading
import structlog
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404

from src.add_api.models import (
    Namespace,
    WorkflowRun,
    GeneratedSpec,
    SpecRepoConfig,
)
from src.add_api.serializers import (
    NamespaceSerializer,
    WorkflowRunSerializer,
    WorkflowStartSerializer,
    WorkflowApproveSerializer,
    WorkflowRejectSerializer,
    GeneratedSpecSerializer,
    SpecRepoConfigSerializer,
    sanitize_state_snapshot,
)

logger = structlog.get_logger()


# --- Workflow Endpoints ---

@api_view(["POST"])
def workflow_start(request):
    """POST /api/v1/workflow/start — Start a new spec-driven workflow."""
    serializer = WorkflowStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user_request = serializer.validated_data["user_request"]
    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

    # Create workflow run in DB
    wf = WorkflowRun.objects.create(
        workflow_id=workflow_id,
        user_request=user_request,
        status=WorkflowRun.Status.RUNNING,
        current_agent="spec_discovery",
    )

    # Run the pipeline in a background thread
    thread = threading.Thread(
        target=_run_pipeline,
        args=(workflow_id, user_request),
        daemon=True,
    )
    thread.start()

    return Response(
        {
            "workflow_id": workflow_id,
            "status": "running",
            "message": "Workflow started. Use WebSocket or polling to track progress.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def workflow_detail(request, workflow_id):
    """GET /api/v1/workflow/{id} — Get workflow status and state."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)
    serializer = WorkflowRunSerializer(wf)
    return Response(serializer.data)


@api_view(["POST"])
def workflow_approve(request, workflow_id):
    """POST /api/v1/workflow/{id}/approve — Approve spec at approval gate."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)

    if wf.status != WorkflowRun.Status.WAITING_APPROVAL:
        return Response(
            {"error": f"Workflow is not waiting for approval. Current status: {wf.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info("workflow_approved", workflow_id=workflow_id)

    # Update state and resume pipeline
    state = wf.state_snapshot
    state["spec_approval_status"] = "approved"

    wf.status = WorkflowRun.Status.RUNNING
    wf.current_agent = "spec_publisher"
    wf.state_snapshot = state
    wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])

    # Resume the graph from the spec approval gate (routes to spec_publisher)
    thread = threading.Thread(
        target=_resume_pipeline,
        args=(workflow_id, state, "spec_approval_gate"),
        daemon=True,
    )
    thread.start()

    return Response({"status": "approved", "message": "Spec approved. Publishing..."})


@api_view(["POST"])
def workflow_reject(request, workflow_id):
    """POST /api/v1/workflow/{id}/reject — Reject spec with feedback."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)

    if wf.status != WorkflowRun.Status.WAITING_APPROVAL:
        return Response(
            {"error": f"Workflow is not waiting for approval. Current status: {wf.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = WorkflowRejectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    feedback = serializer.validated_data["feedback"]

    logger.info("workflow_rejected", workflow_id=workflow_id, feedback=feedback[:100])

    # Update state and resume pipeline from spec_generator
    state = wf.state_snapshot
    state["spec_approval_status"] = "rejected"
    state["spec_rejection_feedback"] = feedback
    state["spec_revision_count"] = state.get("spec_revision_count", 0) + 1

    wf.status = WorkflowRun.Status.RUNNING
    wf.current_agent = "spec_generator"
    wf.state_snapshot = state
    wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])

    # Resume the graph from the spec approval gate (routes to spec_generator,
    # without re-running spec discovery)
    thread = threading.Thread(
        target=_resume_pipeline,
        args=(workflow_id, state, "spec_approval_gate"),
        daemon=True,
    )
    thread.start()

    return Response({"status": "rejected", "message": "Spec rejected. Regenerating with feedback..."})


@api_view(["POST"])
def workflow_cancel(request, workflow_id):
    """POST /api/v1/workflow/{id}/cancel — Cancel workflow permanently."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)

    if wf.status not in [WorkflowRun.Status.WAITING_APPROVAL, WorkflowRun.Status.WAITING_CODE_APPROVAL]:
        return Response(
            {"error": f"Workflow is not waiting for approval. Current status: {wf.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info("workflow_cancelled", workflow_id=workflow_id)

    wf.status = WorkflowRun.Status.CANCELLED
    wf.save(update_fields=["status", "updated_at"])

    # Notify via WebSocket
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"workflow_{workflow_id}",
            {
                "type": "workflow.update",
                "data": {
                    "workflow_id": workflow_id,
                    "current_agent": wf.current_agent,
                    "status": "cancelled",
                    "message": "Workflow cancelled by user.",
                },
            },
        )
    except Exception:
        pass

    return Response({"status": "cancelled", "message": "Workflow cancelled."})


@api_view(["GET"])
def workflow_spec(request, workflow_id):
    """GET /api/v1/workflow/{id}/spec — Get current spec content."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)
    state = wf.state_snapshot
    return Response({
        "spec_id": state.get("spec_id", ""),
        "generated_spec": state.get("generated_spec", ""),
        "low_confidence_sections": state.get("low_confidence_sections", []),
        "duplicate_warning": state.get("duplicate_warning"),
        "consistency_warnings": state.get("consistency_warnings", []),
        "validation_results": state.get("spec_validation_results", []),
        "request_classification": state.get("request_classification", ""),
        "extends_spec": state.get("extends_spec"),
        "related_specs": [
            {"spec_id": rs.get("spec_id"), "score": rs.get("score"), "match_type": rs.get("match_type")}
            for rs in state.get("related_specs", [])
        ],
        "identified_namespaces": state.get("identified_namespaces", []),
        "spec_pr_url": state.get("spec_pr_url"),
        "spec_pr_number": state.get("spec_pr_number"),
    })


@api_view(["GET"])
def workflow_code(request, workflow_id):
    """GET /api/v1/workflow/{id}/code — Get generated code details."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)
    state = sanitize_state_snapshot(wf.state_snapshot)
    return Response({
        "spec_id": state.get("spec_id", ""),
        "implementation_summary": state.get("implementation_summary", ""),
        "generated_files": state.get("generated_files", []),
        "generated_tests": state.get("generated_tests", []),
        "test_results": state.get("test_results", {}),
        "code_pr_url": state.get("code_pr_url"),
        "code_pr_numbers": state.get("code_pr_numbers", []),
        "code_approval_status": state.get("code_approval_status", ""),
        "code_rejection_feedback": state.get("code_rejection_feedback", ""),
        "affected_files": state.get("affected_files", []),
        "target_repositories": state.get("target_repositories", []),
    })


@api_view(["POST"])
def workflow_code_approve(request, workflow_id):
    """POST /api/v1/workflow/{id}/approve-code — Approve code at code approval gate."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)

    if wf.status != WorkflowRun.Status.WAITING_CODE_APPROVAL:
        return Response(
            {"error": f"Workflow is not waiting for code approval. Current status: {wf.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    state = wf.state_snapshot
    state["code_approval_status"] = "approved"

    wf.status = WorkflowRun.Status.RUNNING
    wf.current_agent = "code_review_handoff"
    wf.state_snapshot = state
    wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])

    # Resume the graph from the code approval gate (routes to code_review_handoff)
    thread = threading.Thread(
        target=_resume_pipeline,
        args=(workflow_id, state, "code_approval_gate"),
        daemon=True,
    )
    thread.start()

    return Response({"status": "approved", "message": "Code approved. Merging..."} )


@api_view(["POST"])
def workflow_code_reject(request, workflow_id):
    """POST /api/v1/workflow/{id}/reject-code — Reject code with feedback."""
    wf = get_object_or_404(WorkflowRun, workflow_id=workflow_id)

    if wf.status != WorkflowRun.Status.WAITING_CODE_APPROVAL:
        return Response(
            {"error": f"Workflow is not waiting for code approval. Current status: {wf.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = WorkflowRejectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    feedback = serializer.validated_data["feedback"]

    state = wf.state_snapshot
    state["code_approval_status"] = "rejected"
    state["code_rejection_feedback"] = feedback
    state["code_revision_count"] = state.get("code_revision_count", 0) + 1

    wf.status = WorkflowRun.Status.RUNNING
    wf.current_agent = "code_developer"
    wf.state_snapshot = state
    wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])

    # Resume the graph from the code approval gate (routes to code_developer)
    thread = threading.Thread(
        target=_resume_pipeline,
        args=(workflow_id, state, "code_approval_gate"),
        daemon=True,
    )
    thread.start()

    return Response({"status": "rejected", "message": "Code rejected. Regenerating with feedback..."} )


@api_view(["GET"])
def workflow_list(request):
    """GET /api/v1/workflows — List all workflows with optional status filter."""
    status_filter = request.query_params.get("status")
    qs = WorkflowRun.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)
    serializer = WorkflowRunSerializer(qs[:50], many=True)
    return Response(serializer.data)


# --- Specs & Namespaces ---

class NamespaceViewSet(viewsets.ModelViewSet):
    queryset = Namespace.objects.all()
    serializer_class = NamespaceSerializer
    lookup_field = "pk"


@api_view(["GET"])
def spec_list(request):
    """GET /api/v1/specs — List all generated specs."""
    specs = GeneratedSpec.objects.all()[:100]
    serializer = GeneratedSpecSerializer(specs, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def spec_search(request):
    """POST /api/v1/specs/search — Semantic search across specs."""
    query = request.data.get("query", "")
    if not query:
        return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)

    from src.qdrant_client.service import search_specs
    results = search_specs(query, limit=10)
    return Response({"results": results})


# --- Pipeline Execution Helpers ---

def _apply_result_status(workflow_id: str, result: dict):
    """Persist the final graph result and derive the workflow status from it."""
    wf = WorkflowRun.objects.get(workflow_id=workflow_id)
    # Merge rather than replace: the snapshot carries keys maintained outside
    # the graph (e.g. activity_log) that must survive the final save.
    snapshot = wf.state_snapshot or {}
    snapshot.update(result)
    wf.state_snapshot = snapshot
    wf.current_agent = result.get("current_agent", wf.current_agent)

    if result.get("error"):
        wf.status = WorkflowRun.Status.ERROR
        wf.error = result["error"]
    elif result.get("final_status") in ("completed", "review-failed"):
        # review-failed = merges failed but workflow finished (non-fatal)
        wf.status = WorkflowRun.Status.COMPLETED
    elif result.get("code_approval_status") == "pending":
        wf.status = WorkflowRun.Status.WAITING_CODE_APPROVAL
    elif result.get("spec_approval_status") == "pending":
        wf.status = WorkflowRun.Status.WAITING_APPROVAL
    elif result.get("spec_validation_retry_count", 0) >= settings.MAX_REVISION_CYCLES:
        wf.status = WorkflowRun.Status.FAILED
        wf.error = "Spec validation failed after maximum retries"
    wf.save()


def _mark_workflow_error(workflow_id: str, error: str):
    try:
        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        wf.status = WorkflowRun.Status.ERROR
        wf.error = error
        wf.save()
    except Exception:
        pass


def _run_pipeline(workflow_id: str, user_request: str):
    """Run the full pipeline in a background thread."""
    import django
    django.setup()

    from src.graph.workflow import run_pipeline

    initial_state = {
        "user_request": user_request,
        "workflow_id": workflow_id,
        "spec_validation_retry_count": 0,
        "spec_revision_count": 0,
        "code_revision_count": 0,
        "related_specs": [],
        "identified_namespaces": [],
        "low_confidence_sections": [],
    }

    try:
        logger.info("pipeline_start", workflow_id=workflow_id)
        result = run_pipeline(workflow_id, initial_state)
        logger.info("pipeline_complete", workflow_id=workflow_id, status=result.get("final_status"))
        _apply_result_status(workflow_id, result)
    except Exception as e:
        logger.error("pipeline_error", workflow_id=workflow_id, error=str(e))
        _mark_workflow_error(workflow_id, str(e))


def _resume_pipeline(workflow_id: str, state: dict, gate_node: str):
    """Resume the pipeline after a human decision at an approval gate.

    The graph itself routes from the gate (approved → next stage,
    rejected → revision loop), so no stage sequencing is duplicated here
    and rejections do not re-run earlier stages such as spec discovery.
    """
    import django
    django.setup()

    from src.graph.workflow import resume_from_gate

    try:
        logger.info("pipeline_resume", workflow_id=workflow_id, gate=gate_node)
        result = resume_from_gate(workflow_id, state, gate_node)
        logger.info("pipeline_resumed_complete", workflow_id=workflow_id)
        _apply_result_status(workflow_id, result)
    except Exception as e:
        logger.error("pipeline_resume_error", workflow_id=workflow_id, error=str(e))
        _mark_workflow_error(workflow_id, str(e))
