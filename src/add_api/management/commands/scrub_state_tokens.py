"""Strip repo tokens persisted in WorkflowRun.state_snapshot by older runs.

Runs created before the token-leak fix stored the GitHub PAT inside
target_repositories in the state snapshot. Newer runs never persist it.
"""

from django.core.management.base import BaseCommand
from src.add_api.models import WorkflowRun


class Command(BaseCommand):
    help = "Remove tokens from target_repositories in persisted workflow state snapshots"

    def handle(self, *args, **options):
        cleaned = 0
        for wf in WorkflowRun.objects.all():
            state = wf.state_snapshot or {}
            repos = state.get("target_repositories")
            if not isinstance(repos, list):
                continue
            if not any(isinstance(r, dict) and "token" in r for r in repos):
                continue
            state["target_repositories"] = [
                {k: v for k, v in r.items() if k != "token"} if isinstance(r, dict) else r
                for r in repos
            ]
            wf.state_snapshot = state
            wf.save(update_fields=["state_snapshot", "updated_at"])
            cleaned += 1
        self.stdout.write(self.style.SUCCESS(f"Scrubbed tokens from {cleaned} workflow run(s)."))
