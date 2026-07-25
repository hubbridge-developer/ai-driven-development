"""Code Review Handoff — final validation and merge of code PRs."""

import structlog
import requests
from src.graph.state import WorkflowState
from src.github.service import _headers, GITHUB_API, mark_pull_request_ready

logger = structlog.get_logger()


def code_review_handoff_agent(state: WorkflowState) -> dict:
    """Stage 9: Merge approved code PRs and finalize workflow."""
    from src.graph.workflow import notify_sub_step  # late import to avoid circular dependency
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")
    code_pr_numbers = state.get("code_pr_numbers", [])

    logger.info("code_review_handoff_start",
                workflow_id=workflow_id, prs=len(code_pr_numbers))

    if not code_pr_numbers:
        return {
            "current_agent": "code_review_handoff",
            "merge_results": [],
            "final_status": "completed",
        }

    from django.conf import settings
    token = settings.GITHUB_PAT

    merge_results = []

    notify_sub_step(workflow_id, "code_review_handoff", "Check PR Status", spec_id=spec_id,
                    detail=f"Processing {len(code_pr_numbers)} PR(s) for merge...")

    for pr_info in code_pr_numbers:
        repo_slug = pr_info["repo"]
        pr_number = pr_info["pr_number"]
        owner, repo = repo_slug.split("/", 1)

        # --- Sub-step 1: Check PR Status ---
        notify_sub_step(workflow_id, "code_review_handoff", "Check PR Status", spec_id=spec_id,
                        detail=f"GET /repos/{owner}/{repo}/pulls/{pr_number} — checking state...")

        try:
            # Verify PR is open and mergeable
            pr_resp = requests.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=_headers(token), timeout=30,
            )
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()

            mergeable = pr_data.get("mergeable", "unknown")
            notify_sub_step(workflow_id, "code_review_handoff", "Check PR Status", spec_id=spec_id,
                            detail=f"PR #{pr_number}: state={pr_data['state']}, mergeable={mergeable}")

            if pr_data["state"] != "open":
                notify_sub_step(workflow_id, "code_review_handoff", "Check PR Status", spec_id=spec_id,
                                detail=f"PR #{pr_number} is {pr_data['state']} — skipping merge")
                merge_results.append({
                    "repo": repo_slug,
                    "pr_number": pr_number,
                    "merged": False,
                    "error": f"PR is {pr_data['state']}, not open",
                })
                continue

            # Draft PR = tests were failing at publish time. The human approved
            # at the code gate, which is the explicit override — mark it ready.
            if pr_data.get("draft"):
                notify_sub_step(workflow_id, "code_review_handoff", "Check PR Status", spec_id=spec_id,
                                detail=f"PR #{pr_number} is a draft (tests were failing) — human approved, marking ready...")
                if not mark_pull_request_ready(owner, repo, pr_number, token):
                    merge_results.append({
                        "repo": repo_slug,
                        "pr_number": pr_number,
                        "merged": False,
                        "error": "Could not mark draft PR as ready for review",
                    })
                    continue

            # --- Sub-step 2: Squash Merge ---
            notify_sub_step(workflow_id, "code_review_handoff", "Squash Merge", spec_id=spec_id,
                            detail=f"PUT /repos/{owner}/{repo}/pulls/{pr_number}/merge (squash)...")

            merge_resp = requests.put(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/merge",
                json={
                    "merge_method": "squash",
                    "commit_title": f"[{spec_id}] Code implementation (squash merge)",
                    "commit_message": f"Auto-merged by ADD Code Review Handoff.\n\nSpec: {spec_id}",
                },
                headers=_headers(token), timeout=30,
            )

            if merge_resp.status_code == 200:
                merge_results.append({
                    "repo": repo_slug,
                    "pr_number": pr_number,
                    "merged": True,
                    "error": None,
                })
                notify_sub_step(workflow_id, "code_review_handoff", "Squash Merge", spec_id=spec_id,
                                detail=f"PR #{pr_number} merged successfully into {repo_slug}:main")
                logger.info("code_review_pr_merged",
                            repo=repo_slug, pr_number=pr_number)
            else:
                error_msg = merge_resp.json().get("message", merge_resp.text[:200])
                merge_results.append({
                    "repo": repo_slug,
                    "pr_number": pr_number,
                    "merged": False,
                    "error": error_msg,
                })
                notify_sub_step(workflow_id, "code_review_handoff", "Squash Merge", spec_id=spec_id,
                                detail=f"Merge failed for PR #{pr_number}: {error_msg[:70]}")
                logger.warning("code_review_merge_failed",
                               repo=repo_slug, pr_number=pr_number, error=error_msg)

        except Exception as e:
            merge_results.append({
                "repo": repo_slug,
                "pr_number": pr_number,
                "merged": False,
                "error": str(e),
            })
            notify_sub_step(workflow_id, "code_review_handoff", "Squash Merge", spec_id=spec_id,
                            detail=f"Error processing PR #{pr_number}: {str(e)[:70]}")
            logger.error("code_review_error", repo=repo_slug, error=str(e))

    merged_count = sum(1 for r in merge_results if r.get("merged"))
    failed_count = len(merge_results) - merged_count

    # --- Sub-step 3: Finalize ---
    notify_sub_step(workflow_id, "code_review_handoff", "Finalize", spec_id=spec_id,
                    detail=f"Merged {merged_count}/{len(merge_results)} PR(s)" +
                           (f", {failed_count} failed" if failed_count else " — all successful"))
    notify_sub_step(workflow_id, "code_review_handoff", "Finalize", spec_id=spec_id,
                    detail="Updating workflow status to completed...")

    # Update workflow status
    try:
        from src.add_api.models import WorkflowRun
        wf = WorkflowRun.objects.get(workflow_id=workflow_id)
        wf.status = WorkflowRun.Status.COMPLETED
        wf.save(update_fields=["status", "updated_at"])
    except Exception as e:
        logger.error("code_review_finalize_failed", error=str(e))

    # Send completion WebSocket notification
    _notify_completion(workflow_id, spec_id, merge_results)

    all_merged = all(r.get("merged") for r in merge_results)
    # Merge failures are non-fatal (workflow still completes) but are surfaced
    # in final_status so they are distinguishable from a clean run.
    final_status = "completed" if all_merged else "review-failed"

    logger.info("code_review_handoff_complete",
                workflow_id=workflow_id,
                merged=sum(1 for r in merge_results if r.get("merged")),
                failed=sum(1 for r in merge_results if not r.get("merged")))

    return {
        "current_agent": "code_review_handoff",
        "merge_results": merge_results,
        "final_status": final_status,
    }


def _notify_completion(workflow_id: str, spec_id: str, merge_results: list):
    """Send WebSocket notification for workflow completion."""
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
                    "current_agent": "code_review_handoff",
                    "status": "completed",
                    "spec_id": spec_id,
                    "message": "Workflow completed. Code merged.",
                    "merge_results": merge_results,
                },
            },
        )
    except Exception as e:
        logger.warning("ws_completion_notify_failed", error=str(e))
