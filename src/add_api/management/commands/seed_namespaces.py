"""Seed default namespaces for the POC."""

from django.core.management.base import BaseCommand
from src.add_api.models import Namespace


DEFAULT_NAMESPACES = [
    {
        "name": "auth",
        "description": "Authentication, login, password, sessions, OAuth, JWT tokens",
        "stack_config": {
            "language": "python",
            "framework": "django",
            "test_framework": "pytest",
            "build_tool": "pip",
        },
    },
    {
        "name": "payments",
        "description": "Billing, subscriptions, invoices, payment processing, Stripe",
        "stack_config": {
            "language": "python",
            "framework": "django",
            "test_framework": "pytest",
            "build_tool": "pip",
        },
    },
    {
        "name": "notifications",
        "description": "Email, push notifications, SMS, in-app notifications",
        "stack_config": {
            "language": "python",
            "framework": "django",
            "test_framework": "pytest",
            "build_tool": "pip",
        },
    },
    {
        "name": "user-management",
        "description": "User profiles, roles, permissions, teams, organizations",
        "stack_config": {
            "language": "python",
            "framework": "django",
            "test_framework": "pytest",
            "build_tool": "pip",
        },
    },
]


class Command(BaseCommand):
    help = "Seed default namespaces for the ADD POC"

    def handle(self, *args, **options):
        for ns_data in DEFAULT_NAMESPACES:
            ns, created = Namespace.objects.get_or_create(
                name=ns_data["name"],
                defaults={
                    "description": ns_data["description"],
                    "stack_config": ns_data["stack_config"],
                },
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  {ns.name}: {status}")

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(DEFAULT_NAMESPACES)} namespaces."))
