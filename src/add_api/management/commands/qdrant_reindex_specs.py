"""Reindex all GeneratedSpec rows into Qdrant.

Usage:
  python manage.py qdrant_reindex_specs           # reindex, expect collection to exist
  python manage.py qdrant_reindex_specs --reset   # drop & recreate collection, then reindex

Best run after changing EMBEDDING_MODEL_NAME / VECTOR_DIMENSIONS.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from src.qdrant_client.service import get_qdrant_client, create_collection, index_spec
from src.add_api.models import GeneratedSpec


class Command(BaseCommand):
    help = "Reindex all specifications into Qdrant (optionally reset collection first)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate the Qdrant collection before reindexing (required if dimensions changed).",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        client = get_qdrant_client()
        collection = settings.QDRANT_SPEC_COLLECTION

        if reset:
            self.stdout.write(self.style.WARNING(f"Deleting collection: {collection}"))
            try:
                client.delete_collection(collection)
            except Exception as e:
                self.stdout.write(f"Delete skipped: {e}")
            create_collection()
            self.stdout.write(self.style.SUCCESS(f"Recreated collection: {collection}"))

        specs = list(GeneratedSpec.objects.all())
        total = len(specs)
        if total == 0:
            self.stdout.write("No specs to reindex.")
            return

        self.stdout.write(f"Reindexing {total} specs into '{collection}' ...")
        for idx, spec in enumerate(specs, start=1):
            summary_text = spec.content[:500]  # lightweight summary to avoid LLM calls
            index_spec(
                spec_id=spec.spec_id,
                namespace=spec.namespace,
                spec_content=spec.content,
                summary_text=summary_text,
            )
            if idx % 10 == 0 or idx == total:
                self.stdout.write(f"  {idx}/{total} indexed")

        self.stdout.write(self.style.SUCCESS("Reindex complete."))
