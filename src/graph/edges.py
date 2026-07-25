"""Conditional edge routing functions for the AIDD pipeline."""

from django.conf import settings
from src.graph.state import WorkflowState


def route_after_validator(state: WorkflowState) -> str:
    """Route after spec_validator: valid → approval gate, invalid → retry or END."""
    if state.get("error"):
        return "END"

    # Check if all validations passed
    results = state.get("spec_validation_results", [])
    all_valid = all(r["is_valid"] for r in results)

    if all_valid:
        return "spec_approval_gate"

    retry_count = state.get("spec_validation_retry_count", 0)
    if retry_count < settings.MAX_REVISION_CYCLES:
        return "spec_generator"
    else:
        return "END"


def route_after_approval_gate(state: WorkflowState) -> str:
    """Route after approval gate: approved → publisher, rejected → generator, pending → END (suspend)."""
    if state.get("error"):
        return "END"

    status = state.get("spec_approval_status", "pending")

    if status == "approved":
        return "spec_publisher"
    elif status == "rejected":
        return "spec_generator"
    else:
        # pending — workflow suspends, will be resumed via API
        return "END"


def route_after_code_approval(state: WorkflowState) -> str:
    """Route after code approval gate: approved → review handoff, rejected → code developer, pending → END."""
    if state.get("error"):
        return "END"

    status = state.get("code_approval_status", "pending")

    if status == "approved":
        return "code_review_handoff"
    elif status == "rejected":
        return "code_developer"
    else:
        return "END"
