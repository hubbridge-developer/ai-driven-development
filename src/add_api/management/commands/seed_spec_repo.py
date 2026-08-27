"""Seed SpecRepoConfig from environment variables."""

from django.conf import settings
from django.core.management.base import BaseCommand
from src.add_api.models import SpecRepoConfig


class Command(BaseCommand):
    help = "Seed SpecRepoConfig from SPEC_REPO_URL env var"

    def handle(self, *args, **options):
        # Prefer an explicit SPEC_REPO_URL; otherwise derive it from
        # GITHUB_OWNER + SPEC_REPO_NAME so a deployment only needs those (already
        # set for code publishing). Guarantees SpecRepoConfig is seeded — without
        # it, spec_publisher can't open the spec PR.
        repo_url = settings.SPEC_REPO_URL
        if not repo_url and settings.GITHUB_OWNER and settings.SPEC_REPO_NAME:
            repo_url = f"https://github.com/{settings.GITHUB_OWNER}/{settings.SPEC_REPO_NAME}"
        if not repo_url:
            self.stdout.write(self.style.WARNING(
                "No SPEC_REPO_URL and no GITHUB_OWNER/SPEC_REPO_NAME — skipping."))
            return

        config, created = SpecRepoConfig.objects.get_or_create(
            spec_repo_url=repo_url,
            defaults={
                "branch": "main",
                "active": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created SpecRepoConfig: {repo_url}"))
        else:
            self.stdout.write(f"SpecRepoConfig already exists: {repo_url}")
