"""AIDD LangGraph workflow definition — 10-stage spec + code pipeline."""

import uuid

import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import WorkflowState
from src.graph.edges import (
    route_after_validator,
    route_after_approval_gate,
    route_after_code_approval,
)
from src.agents.spec_discovery import spec_discovery_agent
from src.agents.spec_generator import spec_generator_agent
from src.agents.spec_validator import spec_validator_agent
from src.approval.gate import spec_approval_gate_node, code_approval_gate_node
from src.agents.spec_publisher import spec_publisher_agent
from src.agents.namespace_resolver import namespace_resolver_agent
from src.agents.code_developer import code_developer_agent
from src.agents.code_publisher import code_publisher_agent
from src.agents.code_review_handoff import code_review_handoff_agent

logger = structlog.get_logger()

# Pipeline order — used to determine the next stage after an agent completes
_STAGE_ORDER = [
    # POC 1 stages
    "spec_discovery",
    "spec_generator",
    "spec_validator",
    "spec_approval_gate",
    "spec_publisher",
    # POC 2 stages
    "namespace_resolver",
    "code_developer",
    "code_publisher",
    "code_approval_gate",
    "code_review_handoff",
]


def _next_stage(current: str) -> str:
    """Return the next stage name after the given one."""
    try:
        idx = _STAGE_ORDER.index(current)
        if idx + 1 < len(_STAGE_ORDER):
            return _STAGE_ORDER[idx + 1]
    except ValueError:
        pass
    return current


def _persist_and_notify(agent_fn):
    """Wrap an agent to persist state to DB and send WebSocket notification after execution.

    Saves the NEXT stage as current_agent so the frontend stepper advances immediately.
    """
    def wrapper(state: WorkflowState) -> dict:
        result = agent_fn(state)

        workflow_id = state.get("workflow_id", "")
        completed_agent = result.get("current_agent", "")
        next_agent = _next_stage(completed_agent)

        if workflow_id and completed_agent:
            try:
                from src.aidd_api.models import WorkflowRun
                wf = WorkflowRun.objects.get(workflow_id=workflow_id)
                # Merge result into state_snapshot
                snapshot = wf.state_snapshot or {}
                snapshot.update(result)
                wf.current_agent = next_agent
                wf.state_snapshot = snapshot
                wf.save(update_fields=["current_agent", "state_snapshot", "updated_at"])
                logger.info(
                    "agent_state_persisted",
                    workflow_id=workflow_id,
                    completed=completed_agent,
                    next=next_agent,
                )

                # Send WebSocket notification with the next stage
                _send_ws_update(
                    workflow_id,
                    next_agent,
                    result.get("spec_id", "") or state.get("spec_id", ""),
                )
            except Exception as e:
                logger.error("persist_notify_error", error=str(e), agent=completed_agent)

        return result
    return wrapper


def _send_ws_update(workflow_id: str, current_agent: str, spec_id: str = "",
                    sub_step: str = "", detail: str = "", model: str = ""):
    """Send real-time WebSocket update to the frontend."""
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
                    "current_agent": current_agent,
                    "status": "running",
                    "spec_id": spec_id,
                    "sub_step": sub_step,
                    "detail": detail,
                    "model": model,
                    "message": f"Stage completed: {current_agent}",
                },
            },
        )
        logger.info("ws_update_sent", workflow_id=workflow_id, agent=current_agent, sub_step=sub_step)
    except Exception as e:
        logger.warning("ws_update_failed", workflow_id=workflow_id, error=str(e))


def notify_sub_step(workflow_id: str, agent: str, sub_step: str,
                    spec_id: str = "", detail: str = ""):
    """Send a sub-step progress update via WebSocket.

    Called from within agents to report granular progress to the frontend.
    Also persists the entry to state_snapshot so the activity log survives page reloads.
    """
    if not workflow_id:
        return

    # Resolve LLM model for this agent
    model = ""
    try:
        from src.llm.provider import get_model_for_agent
        model = get_model_for_agent(agent)
    except Exception:
        pass

    # Persist to activity_log in state_snapshot
    try:
        from src.aidd_api.models import WorkflowRun
        from django.utils import timezone

        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        snapshot = wf.state_snapshot or {}
        activity_log = snapshot.get("activity_log", [])
        activity_log.append({
            "agent": agent,
            "sub_step": sub_step,
            "detail": detail or "",
            "model": model,
            "timestamp": timezone.now().isoformat(),
        })
        snapshot["activity_log"] = activity_log
        wf.state_snapshot = snapshot
        wf.save(update_fields=["state_snapshot", "updated_at"])
    except Exception as e:
        logger.warning("activity_log_persist_failed", workflow_id=workflow_id, error=str(e))

    logger.info("sub_step_progress", workflow_id=workflow_id, agent=agent,
                sub_step=sub_step, detail=detail or "")
    _send_ws_update(workflow_id, agent, spec_id=spec_id, sub_step=sub_step,
                    detail=detail, model=model)


def build_workflow() -> StateGraph:
    """Build and compile the AIDD 10-stage pipeline."""
    workflow = StateGraph(WorkflowState)

    # --- POC 1 nodes ---
    workflow.add_node("spec_discovery", _persist_and_notify(spec_discovery_agent))
    workflow.add_node("spec_generator", _persist_and_notify(spec_generator_agent))
    workflow.add_node("spec_validator", _persist_and_notify(spec_validator_agent))
    workflow.add_node("spec_approval_gate", spec_approval_gate_node)  # gate handles its own persistence
    workflow.add_node("spec_publisher", _persist_and_notify(spec_publisher_agent))

    # --- POC 2 nodes ---
    workflow.add_node("namespace_resolver", _persist_and_notify(namespace_resolver_agent))
    workflow.add_node("code_developer", _persist_and_notify(code_developer_agent))
    workflow.add_node("code_publisher", _persist_and_notify(code_publisher_agent))
    workflow.add_node("code_approval_gate", code_approval_gate_node)  # gate handles its own persistence
    workflow.add_node("code_review_handoff", code_review_handoff_agent)  # handles its own persistence

    # Entry point
    workflow.set_entry_point("spec_discovery")

    # --- POC 1 edges ---
    workflow.add_edge("spec_discovery", "spec_generator")
    workflow.add_edge("spec_generator", "spec_validator")

    workflow.add_conditional_edges(
        "spec_validator",
        route_after_validator,
        {
            "spec_approval_gate": "spec_approval_gate",
            "spec_generator": "spec_generator",
            "END": END,
        },
    )

    workflow.add_conditional_edges(
        "spec_approval_gate",
        route_after_approval_gate,
        {
            "spec_publisher": "spec_publisher",
            "spec_generator": "spec_generator",
            "END": END,
        },
    )

    # --- POC 2 edges ---
    # spec_publisher → namespace_resolver (always)
    workflow.add_edge("spec_publisher", "namespace_resolver")

    # namespace_resolver → code_developer (always)
    workflow.add_edge("namespace_resolver", "code_developer")

    # code_developer → code_publisher (always)
    workflow.add_edge("code_developer", "code_publisher")

    # code_publisher → code_approval_gate (always)
    workflow.add_edge("code_publisher", "code_approval_gate")

    # code_approval_gate → code_review_handoff | code_developer | END
    workflow.add_conditional_edges(
        "code_approval_gate",
        route_after_code_approval,
        {
            "code_review_handoff": "code_review_handoff",
            "code_developer": "code_developer",
            "END": END,
        },
    )

    # code_review_handoff → END
    workflow.add_edge("code_review_handoff", END)

    # The checkpointer is only needed so resume_from_gate() can seed a thread
    # and continue mid-graph. Durable state lives in WorkflowRun.state_snapshot,
    # so in-memory checkpoints are fine — resumes survive restarts because each
    # resume re-seeds from the DB snapshot.
    return workflow.compile(checkpointer=MemorySaver())


# Singleton compiled graph
aidd_graph = build_workflow()


def run_pipeline(workflow_id: str, initial_state: dict) -> dict:
    """Run the pipeline from the start for a new workflow."""
    config = {"configurable": {"thread_id": workflow_id}}
    return aidd_graph.invoke(initial_state, config)


def resume_from_gate(workflow_id: str, state: dict, gate_node: str) -> dict:
    """Resume the pipeline after a human decision at an approval gate.

    Seeds a fresh checkpointer thread with the persisted state snapshot as if
    `gate_node` had just run, then lets the graph's own conditional edges route
    onward (approved → next stage, rejected → revision loop). No stages are
    re-executed and no orchestration is duplicated outside the graph.
    """
    # The DB snapshot may carry extra keys (e.g. activity_log) that are not
    # graph channels — only seed the keys the state schema declares.
    channels = WorkflowState.__annotations__.keys()
    seed = {k: v for k, v in state.items() if k in channels}

    config = {"configurable": {"thread_id": f"{workflow_id}:{uuid.uuid4().hex[:8]}"}}
    aidd_graph.update_state(config, seed, as_node=gate_node)
    return aidd_graph.invoke(None, config)
