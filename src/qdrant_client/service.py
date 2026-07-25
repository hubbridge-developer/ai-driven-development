"""Qdrant vector database service — dual-vector indexing and search."""

import hashlib
import structlog
from typing import Optional
from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()

# Embedding model — bge-base-en-v1.5 (768 dimensions)
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
VECTOR_DIMENSIONS = 768

# Lazy-loaded singletons
_client: Optional[QdrantClient] = None
_embedder: Optional[SentenceTransformer] = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def embed_text(text: str) -> list[float]:
    """Generate embedding vector for a text string."""
    embedder = get_embedder()
    return embedder.encode(text).tolist()


def create_collection():
    """Create the spec_embeddings collection if it doesn't exist."""
    client = get_qdrant_client()
    collection_name = settings.QDRANT_SPEC_COLLECTION

    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_DIMENSIONS, distance=Distance.COSINE
            ),
        )
        logger.info("qdrant_collection_created", collection=collection_name)
    else:
        logger.info("qdrant_collection_exists", collection=collection_name)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def index_spec(spec_id: str, namespace: str, spec_content: str, summary_text: str):
    """Index a spec with dual vectors: 1 summary + N section vectors.

    Uses delete-before-upsert to prevent stale vectors.
    """
    client = get_qdrant_client()
    collection = settings.QDRANT_SPEC_COLLECTION

    # Delete existing vectors for this spec_id
    try:
        client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key="spec_id", match=MatchValue(value=spec_id))]
            ),
        )
    except Exception:
        pass  # Collection might be empty

    points = []
    base_id = int(hashlib.md5(spec_id.encode()).hexdigest()[:8], 16)

    # Vector 1: Summary vector
    summary_vector = embed_text(summary_text)
    points.append(
        PointStruct(
            id=base_id,
            vector=summary_vector,
            payload={
                "spec_id": spec_id,
                "namespace": namespace,
                "type": "summary",
                "content_hash": content_hash(spec_content),
            },
        )
    )

    # Vector 2+: Section vectors
    sections = _extract_sections(spec_content)
    for idx, (section_name, section_text) in enumerate(sections.items(), start=1):
        if not section_text.strip():
            continue
        section_vector = embed_text(section_text)
        points.append(
            PointStruct(
                id=base_id + idx,
                vector=section_vector,
                payload={
                    "spec_id": spec_id,
                    "namespace": namespace,
                    "type": section_name,
                    "content_hash": content_hash(section_text),
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    logger.info(
        "spec_indexed",
        spec_id=spec_id,
        namespace=namespace,
        vectors_count=len(points),
    )


def search_specs(
    query_text: str,
    namespace_filter: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Dual-vector search: query both summary and section vectors.

    Returns deduplicated results with highest score per spec_id.
    """
    client = get_qdrant_client()
    collection = settings.QDRANT_SPEC_COLLECTION

    # Check if collection has any points
    try:
        info = client.get_collection(collection)
        if info.points_count == 0:
            logger.info("qdrant_search_empty_collection")
            return []
    except Exception as e:
        logger.warning("qdrant_search_error", error=str(e))
        return []

    query_vector = embed_text(query_text)

    # Build filter
    search_filter = None
    if namespace_filter:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="namespace", match=MatchValue(value=namespace_filter)
                )
            ]
        )

    results = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=limit * 2,  # Over-fetch to account for dedup
    )

    # Deduplicate: keep highest score per spec_id
    best_per_spec: dict[str, dict] = {}
    for hit in results:
        spec_id = hit.payload["spec_id"]
        score = hit.score
        if spec_id not in best_per_spec or score > best_per_spec[spec_id]["score"]:
            best_per_spec[spec_id] = {
                "spec_id": spec_id,
                "score": score,
                "match_type": hit.payload.get("type", "unknown"),
                "namespace": hit.payload.get("namespace", ""),
            }

    # Sort by score descending and apply limit
    sorted_results = sorted(
        best_per_spec.values(), key=lambda x: x["score"], reverse=True
    )[:limit]

    logger.info(
        "qdrant_search_complete",
        query_length=len(query_text),
        results_count=len(sorted_results),
    )
    return sorted_results


def _extract_sections(spec_content: str) -> dict[str, str]:
    """Extract XML-tagged sections from spec content."""
    import re

    sections = {}
    tag_names = [
        "summary",
        "requirements",
        "technical_design",
        "acceptance_criteria",
        "background",
        "dependencies",
    ]
    for tag in tag_names:
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, spec_content, re.DOTALL)
        if match:
            sections[tag] = match.group(1).strip()
    return sections
