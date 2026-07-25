"""Seed SpecRepoConfig from environment variables."""

from django.conf import settings
from django.core.management.base import BaseCommand
from src.add_api.models import SpecRepoConfig


class Command(BaseCommand):
    help = "Seed SpecRepoConfig from SPEC_REPO_URL env var"

    def handle(self, *args, **options):
        repo_url = settings.SPEC_REPO_URL
        if not repo_url:
            self.stdout.write(self.style.WARNING("SPEC_REPO_URL not set, skipping."))
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
