"""Management command to create the Qdrant spec_embeddings collection."""

from django.core.management.base import BaseCommand
from src.qdrant_client.service import create_collection


class Command(BaseCommand):
    help = "Create the Qdrant spec_embeddings collection"

    def handle(self, *args, **options):
        try:
            create_collection()
            self.stdout.write(self.style.SUCCESS("Qdrant collection ready."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Qdrant not available yet: {e}"))
            self.stdout.write("Collection will be created on first use.")
