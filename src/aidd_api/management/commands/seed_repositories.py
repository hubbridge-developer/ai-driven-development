"""Seed Repository records linking namespaces to code repositories."""

from django.conf import settings
from django.core.management.base import BaseCommand
from src.aidd_api.models import Namespace, Repository


# Namespaces that should point at the configured code repo. The actual repo
# slug is resolved from settings (GITHUB_OWNER + CODE_REPO) so a new deployment
# only has to set env vars — no code edits.
DEFAULT_REPO_NAMESPACES = ["auth", "user-management"]


class Command(BaseCommand):
    help = "Seed Repository records linking namespaces to code repos"

    def handle(self, *args, **options):
        repo_slug = settings.qualify_repo(settings.CODE_REPO)
        default_repositories = {ns: repo_slug for ns in DEFAULT_REPO_NAMESPACES}
        for ns_name, repo_slug in default_repositories.items():
            try:
                ns = Namespace.objects.get(name=ns_name)
            except Namespace.DoesNotExist:
                self.stdout.write(f"  {ns_name}: namespace not found, skipping")
                continue

            repo, created = Repository.objects.get_or_create(
                namespace=ns,
                repo_slug=repo_slug,
                defaults={"paths": []},
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  {ns_name} → {repo_slug}: {status}")

        self.stdout.write(self.style.SUCCESS("Repository seeding complete."))
