"""Management command to reset Qdrant — delete and recreate the collection."""

from django.conf import settings
from django.core.management.base import BaseCommand
from src.qdrant_client.service import get_qdrant_client, create_collection


class Command(BaseCommand):
    help = "Delete and recreate the Qdrant spec_embeddings collection (full reset)"

    def handle(self, *args, **options):
        client = get_qdrant_client()
        collection = settings.QDRANT_SPEC_COLLECTION

        try:
            client.delete_collection(collection)
            self.stdout.write(f"Deleted collection: {collection}")
        except Exception as e:
            self.stdout.write(f"Delete skipped: {e}")

        create_collection()
        self.stdout.write(self.style.SUCCESS("Qdrant reset complete. Collection is empty and ready."))
