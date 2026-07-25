"""Sub-agent: Consistency Checker — validates the new spec against existing specs
in the namespace for contradictions or unintended duplications.

Uses sentence-transformers embeddings + Qdrant search (no LLM).
Compares at both spec-level (summary) and section-level granularity.

Source of truth: Qdrant (not PostgreSQL). Qdrant holds all indexed spec vectors,
so even if DB records are removed, Qdrant still has the vectors for comparison."""

import re
import structlog
from django.conf import settings
from src.qdrant_client.service import search_specs, _extract_sections

logger = structlog.get_logger()

# Thresholds for consistency checking
DUPLICATE_THRESHOLD = float(getattr(settings, "DUPLICATE_SIMILARITY_THRESHOLD", 0.85))
OVERLAP_THRESHOLD = 0.70  # Section-level overlap warning


def check_consistency(
    generated_spec: str,
    spec_id: str,
    namespace: str,
    related_specs: list[dict],
) -> dict:
    """Check the generated spec against existing specs in Qdrant.

    Uses dual-vector search:
    1. Embed the full spec summary → search Qdrant for spec-level duplicates
    2. Embed each section → search Qdrant for section-level overlaps

    Returns:
        dict with keys: duplicate_warning, consistency_warnings
    """
    logger.info(
        "consistency_checker_start",
        spec_id=spec_id,
        namespace=namespace,
    )

    try:
        duplicate_warning = None
        warnings = []

        # --- Check 1: Spec-level duplicate detection ---
        # Extract summary section and embed it, search Qdrant
        summary_text = _extract_summary(generated_spec)
        if summary_text:
            # Search across ALL namespaces — duplicates can exist in different namespaces
            summary_results = search_specs(
                query_text=summary_text,
                namespace_filter=None,
                limit=5,
            )

            # Log all results for debugging
            for result in summary_results:
                logger.info(
                    "consistency_check_result",
                    check="summary",
                    spec_id=spec_id,
                    matched_spec=result["spec_id"],
                    score=round(result["score"], 4),
                    match_type=result["match_type"],
                )

            for result in summary_results:
                if result["spec_id"] == spec_id:
                    continue
                score = result["score"]

                if score >= DUPLICATE_THRESHOLD:
                    duplicate_warning = (
                        f"Consistency Check: This spec is highly similar to "
                        f"{result['spec_id']} (similarity: {score:.3f}). "
                        f"Consider updating the existing spec instead of creating a new one."
                    )
                elif score >= OVERLAP_THRESHOLD:
                    warnings.append(
                        f"Spec-level overlap with {result['spec_id']} "
                        f"(similarity: {score:.3f}, matched on: {result['match_type']})"
                    )

        # --- Check 2: Section-level overlap detection ---
        sections = _extract_sections(generated_spec)
        for section_name, section_text in sections.items():
            if not section_text.strip() or section_name == "spec_header":
                continue

            section_results = search_specs(
                query_text=section_text,
                namespace_filter=None,
                limit=3,
            )

            for result in section_results:
                if result["spec_id"] == spec_id:
                    continue
                score = result["score"]

                logger.info(
                    "consistency_check_result",
                    check=section_name,
                    spec_id=spec_id,
                    matched_spec=result["spec_id"],
                    score=round(score, 4),
                    match_type=result["match_type"],
                )

                if score >= OVERLAP_THRESHOLD:
                    warnings.append(
                        f"Section <{section_name}> overlaps with {result['spec_id']} "
                        f"(similarity: {score:.3f}, matched on: {result['match_type']})"
                    )

        # Deduplicate warnings
        warnings = list(dict.fromkeys(warnings))

        logger.info(
            "consistency_checker_complete",
            is_duplicate=duplicate_warning is not None,
            warning_count=len(warnings),
        )

        return {
            "duplicate_warning": duplicate_warning,
            "consistency_warnings": warnings,
        }

    except Exception as e:
        logger.warning("consistency_checker_error", error=str(e))
        return {"duplicate_warning": None, "consistency_warnings": []}


def _extract_summary(spec_content: str) -> str:
    """Extract the <summary> section text from a spec."""
    match = re.search(r"<summary>(.*?)</summary>", spec_content, re.DOTALL)
    return match.group(1).strip() if match else ""
