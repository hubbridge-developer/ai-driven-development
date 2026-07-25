"""Agent 1 — Spec Discovery: search for related/duplicate specs via Qdrant."""

import structlog
from django.conf import settings
from src.graph.state import WorkflowState
from src.llm.provider import call_llm
from src.qdrant_client.service import search_specs
from src.aidd_api.models import Namespace, GeneratedSpec

logger = structlog.get_logger()

PARSE_REQUEST_PROMPT = """Analyze the following user request and extract structured information.

User Request: "{user_request}"

Extract the following as a JSON object:
{{
    "intent": "what the user wants to achieve",
    "domain_keywords": ["list", "of", "technical", "and", "business", "terms"],
    "affected_areas": ["which", "system", "domains", "are", "involved"],
    "request_type": "new_feature | update | bugfix"
}}

Return ONLY the JSON object, no other text."""

QUERY_EXPANSION_PROMPT = """Expand the following terse user request into a richer semantic description.
The expanded version should capture implied concepts and related technical terms
to improve search recall over a specification repository.

User Request: "{user_request}"

Return ONLY the expanded description, no other text. Keep it under 100 words."""


def spec_discovery_agent(state: WorkflowState) -> dict:
    """Search for existing specifications related to the user's request."""
    user_request = state["user_request"]
    workflow_id = state.get("workflow_id", "")
    logger.info("spec_discovery_start", request=user_request[:100])

    from src.graph.workflow import notify_sub_step

    try:
        # Step 1: Parse user request via LLM
        notify_sub_step(workflow_id, "spec_discovery", "LLM Request Parsing",
                        detail=f"Sending request to LLM: \"{user_request[:80]}...\"")
        parse_response = call_llm(
            prompt=PARSE_REQUEST_PROMPT.format(user_request=user_request),
            system_prompt="You are a requirements analyst. Extract structured information from user requests.",
            agent_name="spec_discovery",
            max_tokens=512,
        )
        parsed = _parse_json_response(parse_response.content)
        notify_sub_step(workflow_id, "spec_discovery", "LLM Request Parsing",
                        detail=f"Intent: {parsed.get('intent', '?')[:60]}")
        notify_sub_step(workflow_id, "spec_discovery", "LLM Request Parsing",
                        detail=f"Keywords: {', '.join(parsed.get('domain_keywords', [])[:6])}")
        notify_sub_step(workflow_id, "spec_discovery", "LLM Request Parsing",
                        detail=f"Type: {parsed.get('request_type', '?')} | Areas: {', '.join(parsed.get('affected_areas', [])[:4])}")

        # Step 2: Determine namespace
        all_ns = list(Namespace.objects.values_list("name", flat=True))
        notify_sub_step(workflow_id, "spec_discovery", "Namespace Resolution",
                        detail=f"Checking {len(all_ns)} registered namespace(s): {', '.join(all_ns[:5])}")
        identified_namespaces = _resolve_namespaces(
            parsed.get("affected_areas", []),
            parsed.get("domain_keywords", []),
        )
        if identified_namespaces:
            notify_sub_step(workflow_id, "spec_discovery", "Namespace Resolution",
                            detail=f"Matched: {', '.join(identified_namespaces)}")
        else:
            notify_sub_step(workflow_id, "spec_discovery", "Namespace Resolution",
                            detail="No namespace match — will use 'general'")

        # Step 3: Optionally expand query for better recall
        search_query = user_request
        if settings.ENABLE_QUERY_EXPANSION:
            notify_sub_step(workflow_id, "spec_discovery", "LLM Query Expansion",
                            detail="Calling LLM to enrich query with implied concepts...")
            try:
                expansion = call_llm(
                    prompt=QUERY_EXPANSION_PROMPT.format(user_request=user_request),
                    agent_name="spec_discovery",
                    max_tokens=256,
                )
                search_query = expansion.content.strip()
                notify_sub_step(workflow_id, "spec_discovery", "LLM Query Expansion",
                                detail=f"Expanded: \"{search_query[:90]}...\"")
            except Exception:
                notify_sub_step(workflow_id, "spec_discovery", "LLM Query Expansion",
                                detail="Expansion failed, falling back to original query")

        # Step 4: Dual-vector search in Qdrant
        notify_sub_step(workflow_id, "spec_discovery", "Qdrant Dual-Vector Search",
                        detail="Querying Qdrant collection (content + summary vectors, top-10)...")
        search_results = search_specs(search_query, limit=10)
        notify_sub_step(workflow_id, "spec_discovery", "Qdrant Dual-Vector Search",
                        detail=f"Returned {len(search_results)} result(s) from vector search")

        # Step 5: Enrich with full spec content for related specs
        notify_sub_step(workflow_id, "spec_discovery", "Related Spec Enrichment",
                        detail=f"Processing {len(search_results)} results — fetching content, checking duplicates")
        related_specs = []
        duplicate_warning = None
        extends_spec = None

        for idx, result in enumerate(search_results):
            score = result["score"]

            logger.info(
                "discovery_search_result",
                spec_id=result["spec_id"],
                score=round(score, 4),
                match_type=result["match_type"],
                relevance_threshold=settings.RELEVANCE_THRESHOLD,
                related_threshold=settings.RELATED_SPEC_THRESHOLD,
            )

            relevance = "relevant" if score >= settings.RELEVANCE_THRESHOLD else "below threshold"
            notify_sub_step(workflow_id, "spec_discovery", "Related Spec Enrichment",
                            detail=f"[{idx+1}/{len(search_results)}] {result['spec_id']} — score {score:.3f} ({result['match_type']}) → {relevance}")

            if score < settings.RELEVANCE_THRESHOLD:
                continue

            # Fetch full spec content from DB
            spec_content = _fetch_spec_content(result["spec_id"])
            entry = {
                "spec_id": result["spec_id"],
                "score": score,
                "match_type": result["match_type"],
                "content": spec_content or "",
            }

            # Duplicate detection
            if score >= settings.DUPLICATE_SIMILARITY_THRESHOLD:
                duplicate_warning = (
                    f"A highly similar spec already exists: {result['spec_id']} "
                    f"with similarity {score:.2f}. Consider updating the existing spec instead."
                )
                extends_spec = result["spec_id"]
                notify_sub_step(workflow_id, "spec_discovery", "Related Spec Enrichment",
                                detail=f"⚠ Duplicate detected: {result['spec_id']} (score {score:.2f})")

            if score >= settings.RELATED_SPEC_THRESHOLD:
                related_specs.append(entry)

        notify_sub_step(workflow_id, "spec_discovery", "Related Spec Enrichment",
                        detail=f"Done — {len(related_specs)} related spec(s), duplicate={'yes' if duplicate_warning else 'no'}")

        # Step 6: Classification
        request_classification = parsed.get("request_type", "new_feature")
        if request_classification == "new_feature":
            request_classification = "new"

        logger.info(
            "spec_discovery_complete",
            namespaces=identified_namespaces,
            related_count=len(related_specs),
            classification=request_classification,
            has_duplicate=duplicate_warning is not None,
        )

        return {
            "related_specs": related_specs,
            "identified_namespaces": identified_namespaces,
            "request_classification": request_classification,
            "extends_spec": extends_spec,
            "duplicate_warning": duplicate_warning,
            "current_agent": "spec_discovery",
        }

    except Exception as e:
        logger.error("spec_discovery_error", error=str(e))
        return {
            "related_specs": [],
            "identified_namespaces": [],
            "request_classification": "new",
            "extends_spec": None,
            "duplicate_warning": None,
            "current_agent": "spec_discovery",
            "error": f"Spec discovery failed: {str(e)}",
        }


def _resolve_namespaces(
    affected_areas: list[str], keywords: list[str]
) -> list[str]:
    """Match affected areas/keywords against known namespaces in DB."""
    all_namespaces = Namespace.objects.all()
    if not all_namespaces.exists():
        return []

    matched = []
    search_terms = [a.lower() for a in affected_areas + keywords]

    for ns in all_namespaces:
        ns_name = ns.name.lower()
        ns_desc = ns.description.lower()
        for term in search_terms:
            if term in ns_name or term in ns_desc or ns_name in term:
                if ns.name not in matched:
                    matched.append(ns.name)
                break

    return matched


def _fetch_spec_content(spec_id: str) -> str:
    """Fetch full spec content from GeneratedSpec model."""
    try:
        spec = GeneratedSpec.objects.filter(spec_id=spec_id).order_by("-version").first()
        return spec.content if spec else ""
    except Exception:
        return ""


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    import json
    import re

    # Strip markdown code fences if present
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"intent": "", "domain_keywords": [], "affected_areas": [], "request_type": "new_feature"}
