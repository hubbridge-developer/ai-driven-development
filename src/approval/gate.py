"""Approval Gate 1 — Specification Review: pause workflow for human approval."""

import structlog
from src.graph.state import WorkflowState
from src.add_api.models import WorkflowRun

logger = structlog.get_logger()


def spec_approval_gate_node(state: WorkflowState) -> dict:
    """Pause workflow and wait for human approval/rejection.

    The workflow suspends here. State is persisted to PostgreSQL.
    The user approves or rejects via the REST API, which updates the
    WorkflowRun and resumes the graph.
    """
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")

    logger.info("approval_gate_entered", workflow_id=workflow_id, spec_id=spec_id)

    from src.graph.workflow import notify_sub_step
    notify_sub_step(workflow_id, "spec_approval_gate", "Persist State", spec_id=spec_id,
                    detail=f"Saving workflow state to PostgreSQL ({spec_id})...")

    # Persist state to DB — mark workflow as waiting for approval
    try:
        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        wf.status = WorkflowRun.Status.WAITING_APPROVAL
        wf.current_agent = "spec_approval_gate"
        # Merge, don't replace: the snapshot carries keys maintained outside
        # the graph (activity_log) that must survive the gate persist.
        snapshot = wf.state_snapshot or {}
        snapshot.update(dict(state))
        wf.state_snapshot = snapshot
        wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])
        notify_sub_step(workflow_id, "spec_approval_gate", "Persist State", spec_id=spec_id,
                        detail="State persisted — workflow paused for human review")
    except WorkflowRun.DoesNotExist:
        logger.error("approval_gate_workflow_not_found", workflow_id=workflow_id)

    # Send WebSocket notification
    dup = state.get("duplicate_warning")
    lcs = state.get("low_confidence_sections", [])
    review_detail = f"Spec {spec_id} ready for review"
    if dup:
        review_detail += " (duplicate warning)"
    if lcs:
        review_detail += f" ({len(lcs)} low-confidence section(s))"
    notify_sub_step(workflow_id, "spec_approval_gate", "Human Review", spec_id=spec_id,
                    detail=review_detail)
    _notify_approval_needed(workflow_id, spec_id, state)

    # Return pending status — route_after_approval_gate will send to END (suspend)
    return {
        "spec_approval_status": "pending",
        "current_agent": "spec_approval_gate",
    }


def code_approval_gate_node(state: WorkflowState) -> dict:
    """Pause workflow and wait for human approval of generated code."""
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")

    logger.info("code_approval_gate_entered", workflow_id=workflow_id, spec_id=spec_id)

    from src.graph.workflow import notify_sub_step
    notify_sub_step(workflow_id, "code_approval_gate", "Persist State", spec_id=spec_id,
                    detail=f"Saving code generation state to PostgreSQL ({spec_id})...")

    # Persist state to DB — mark workflow as waiting for code approval
    try:
        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        wf.status = WorkflowRun.Status.WAITING_CODE_APPROVAL
        wf.current_agent = "code_approval_gate"
        # Merge, don't replace — see spec gate above.
        snapshot = wf.state_snapshot or {}
        snapshot.update(dict(state))
        wf.state_snapshot = snapshot
        wf.save(update_fields=["status", "current_agent", "state_snapshot", "updated_at"])
        notify_sub_step(workflow_id, "code_approval_gate", "Persist State", spec_id=spec_id,
                        detail="State persisted — workflow paused for code review")
    except WorkflowRun.DoesNotExist:
        logger.error("code_approval_gate_workflow_not_found", workflow_id=workflow_id)

    # Send WebSocket notification
    files_count = len(state.get("generated_files", []))
    tests_count = len(state.get("generated_tests", []))
    pr_url = state.get("code_pr_url", "")
    review_detail = f"Code ready for review: {files_count} files, {tests_count} tests"
    if pr_url:
        review_detail += f" — PR: {pr_url}"
    notify_sub_step(workflow_id, "code_approval_gate", "Human Review", spec_id=spec_id,
                    detail=review_detail)
    _notify_code_approval_needed(workflow_id, spec_id, state)

    return {
        "code_approval_status": "pending",
        "current_agent": "code_approval_gate",
    }


def _notify_code_approval_needed(workflow_id: str, spec_id: str, state: dict):
    """Send WebSocket notification that code approval is needed."""
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
                    "current_agent": "code_approval_gate",
                    "status": "waiting_code_approval",
                    "spec_id": spec_id,
                    "sub_step": "Human Review",
                    "message": f"Code for {spec_id} is ready for review.",
                    "code_pr_url": state.get("code_pr_url"),
                    "implementation_summary": state.get("implementation_summary", ""),
                },
            },
        )
    except Exception as e:
        logger.warning("websocket_code_notify_failed", error=str(e))


def _notify_approval_needed(workflow_id: str, spec_id: str, state: dict):
    """Send WebSocket notification that approval is needed."""
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
                    "current_agent": "spec_approval_gate",
                    "status": "waiting_approval",
                    "spec_id": spec_id,
                    "sub_step": "Human Review",
                    "message": f"Specification {spec_id} is ready for review.",
                    "duplicate_warning": state.get("duplicate_warning"),
                    "low_confidence_sections": state.get("low_confidence_sections", []),
                },
            },
        )
    except Exception as e:
        logger.warning("websocket_notify_failed", error=str(e))
