"""Agent 3 — Spec Publisher: publish approved spec to GitHub and index into Qdrant.

Flow:
  1. Save spec to PostgreSQL (GeneratedSpec)
  2. Publish to GitHub: create branch → commit rendered markdown → open PR
  3. Generate LLM summary for Qdrant indexing
  4. Index dual vectors into Qdrant (non-fatal)
  5. Update workflow status and notify via WebSocket
"""

import structlog
from django.conf import settings
from django.utils import timezone
from src.graph.state import WorkflowState
from src.llm.provider import call_llm
from src.qdrant_client.service import index_spec
from src.aidd_api.models import WorkflowRun, GeneratedSpec, SpecRepoConfig
from src.github.service import publish_spec_to_github

logger = structlog.get_logger()

SUMMARIZE_PROMPT = """Summarize the following specification in a single paragraph (under 100 words).
Focus on what the spec is about, the main feature, and key technical aspects.

Specification:
{spec_content}

Return ONLY the summary paragraph, no other text."""


def spec_publisher_agent(state: WorkflowState) -> dict:
    """Publish the approved spec: save to DB, push to GitHub, index into Qdrant."""
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")
    generated_spec = state.get("generated_spec", "")
    user_request = state.get("user_request", "")
    namespace = ""
    namespaces = state.get("identified_namespaces", [])
    if namespaces:
        namespace = namespaces[0]

    logger.info("spec_publisher_start", workflow_id=workflow_id, spec_id=spec_id)

    spec_pr_url = None
    spec_pr_number = None

    from src.graph.workflow import notify_sub_step

    try:
        # Step 1: Save spec to database
        notify_sub_step(workflow_id, "spec_publisher", "Save to Database", spec_id=spec_id,
                        detail=f"Writing {spec_id} to PostgreSQL (namespace: {namespace or 'default'}, {len(generated_spec)} chars)...")
        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        spec_record = GeneratedSpec.objects.create(
            workflow_run=wf,
            spec_id=spec_id,
            namespace=namespace,
            content=generated_spec,
        )
        notify_sub_step(workflow_id, "spec_publisher", "Save to Database", spec_id=spec_id,
                        detail=f"Saved {spec_id} v{spec_record.version} (id: {str(spec_record.id)[:8]}...)")

        # Step 2: Publish to GitHub — create branch, commit spec, open PR
        notify_sub_step(workflow_id, "spec_publisher", "GitHub Publish (Branch / Commit / PR)", spec_id=spec_id,
                        detail=f"Checking GitHub configuration...")
        github_result = _publish_to_github(spec_id, namespace, generated_spec, user_request)
        if github_result:
            spec_pr_url = github_result.get("spec_pr_url")
            spec_pr_number = github_result.get("spec_pr_number")
            notify_sub_step(workflow_id, "spec_publisher", "GitHub Publish (Branch / Commit / PR)", spec_id=spec_id,
                            detail=f"PR #{spec_pr_number} created: {spec_pr_url}")
        else:
            notify_sub_step(workflow_id, "spec_publisher", "GitHub Publish (Branch / Commit / PR)", spec_id=spec_id,
                            detail="GitHub not configured or publish skipped — spec saved to DB only")

        # Step 3: Generate summary for Qdrant indexing via LLM
        notify_sub_step(workflow_id, "spec_publisher", "LLM Summary for Indexing", spec_id=spec_id,
                        detail="Calling LLM to generate a concise summary for vector indexing...")
        summary_text = _generate_summary(generated_spec)
        notify_sub_step(workflow_id, "spec_publisher", "LLM Summary for Indexing", spec_id=spec_id,
                        detail=f"Summary: \"{summary_text[:90]}...\"")

        # Step 4: Index into Qdrant (non-fatal)
        notify_sub_step(workflow_id, "spec_publisher", "Qdrant Vector Indexing", spec_id=spec_id,
                        detail=f"Encoding dual vectors (content + summary) for {spec_id}...")
        try:
            index_spec(
                spec_id=spec_id,
                namespace=namespace,
                spec_content=generated_spec,
                summary_text=summary_text,
            )
            spec_record.indexed_at = timezone.now()
            spec_record.save(update_fields=["indexed_at"])
            notify_sub_step(workflow_id, "spec_publisher", "Qdrant Vector Indexing", spec_id=spec_id,
                            detail=f"Indexed successfully at {spec_record.indexed_at.strftime('%H:%M:%S')}")
            logger.info("spec_indexed_to_qdrant", spec_id=spec_id)
        except Exception as e:
            notify_sub_step(workflow_id, "spec_publisher", "Qdrant Vector Indexing", spec_id=spec_id,
                            detail=f"Indexing failed (non-fatal): {str(e)[:80]}")
            logger.warning("spec_qdrant_indexing_failed", spec_id=spec_id, error=str(e))

        # Step 5: Update workflow status
        wf.state_snapshot = dict(state)
        wf.state_snapshot["spec_pr_url"] = spec_pr_url
        wf.state_snapshot["spec_pr_number"] = spec_pr_number
        # Keep workflow running; current_agent will be set by the wrapper
        if wf.status != WorkflowRun.Status.RUNNING:
            wf.status = WorkflowRun.Status.RUNNING
        wf.save(update_fields=["status", "state_snapshot", "updated_at"])

        # Step 6: Notify via WebSocket
        _notify_spec_published(workflow_id, spec_id, spec_pr_url)

        logger.info(
            "spec_publisher_complete",
            spec_id=spec_id,
            namespace=namespace,
            pr_url=spec_pr_url,
            pr_number=spec_pr_number,
        )

        return {
            "spec_published": True,
            "spec_pr_url": spec_pr_url,
            "spec_pr_number": spec_pr_number,
            "current_agent": "spec_publisher",
        }

    except Exception as e:
        logger.error("spec_publisher_error", error=str(e))
        return {
            "spec_published": False,
            "spec_pr_url": None,
            "spec_pr_number": None,
            "current_agent": "spec_publisher",
            "error": f"Spec publishing failed: {str(e)}",
        }


def _publish_to_github(
    spec_id: str,
    namespace: str,
    spec_content: str,
    user_request: str,
) -> dict | None:
    """Publish spec to GitHub. Returns PR info or None if GitHub is not configured."""
    # Try SpecRepoConfig from DB first, fall back to env vars
    repo_url = ""
    base_branch = "main"
    token = ""

    try:
        config = SpecRepoConfig.objects.filter(active=True).first()
        if config:
            repo_url = config.spec_repo_url
            base_branch = config.branch or "main"
            # Token from DB (encrypted) or fall back to env
            token = settings.GITHUB_PAT
    except Exception:
        pass

    # Fall back to env vars
    if not repo_url:
        repo_url = settings.SPEC_REPO_URL
    if not token:
        token = settings.GITHUB_PAT

    if not repo_url or not token:
        logger.info("github_publish_skip", reason="SPEC_REPO_URL or GITHUB_PAT not configured")
        return None

    try:
        return publish_spec_to_github(
            spec_id=spec_id,
            namespace=namespace,
            spec_content=spec_content,
            user_request=user_request,
            repo_url=repo_url,
            base_branch=base_branch,
            token=token,
        )
    except Exception as e:
        logger.error("github_publish_failed", spec_id=spec_id, error=str(e))
        # GitHub failure is non-fatal for the POC — spec is still saved to DB and Qdrant
        return None


def _generate_summary(spec_content: str) -> str:
    """Generate an LLM summary for Qdrant indexing. Falls back to first 500 chars."""
    try:
        response = call_llm(
            prompt=SUMMARIZE_PROMPT.format(spec_content=spec_content[:3000]),
            agent_name="spec_publisher",
            max_tokens=256,
        )
        return response.content.strip()
    except Exception:
        return spec_content[:500]


def _notify_spec_published(workflow_id: str, spec_id: str, pr_url: str | None):
    """Send WebSocket notification that spec is published."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        message = f"Specification {spec_id} published and indexed."
        if pr_url:
            message += f" PR: {pr_url}"

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"workflow_{workflow_id}",
            {
                "type": "workflow.update",
                "data": {
                    "workflow_id": workflow_id,
                    "current_agent": "spec_publisher",
                    "status": "running",
                    "spec_id": spec_id,
                    "spec_pr_url": pr_url,
                    "message": message,
                },
            },
        )
    except Exception as e:
        logger.warning("websocket_notify_failed", error=str(e))
