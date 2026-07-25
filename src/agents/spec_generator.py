"""Agent 2 — Spec Generation: generate or update specs using LLM.

Sub-Agents:
  - Consistency Checker (sub_agents/consistency_checker.py) — validates the new spec
    against existing specs in the namespace for contradictions or unintended duplications.
"""

import structlog
from src.graph.state import WorkflowState
from src.llm.provider import call_llm
from src.aidd_api.models import Namespace
from src.agents.sub_agents.consistency_checker import check_consistency

logger = structlog.get_logger()

SPEC_GENERATION_SYSTEM_PROMPT = """You are a specification writer. You output ONLY XML content with YAML inside each tag. No markdown, no explanation, no code fences.

Here is an EXAMPLE of a correct specification:

<spec_header>
format_version: 2
spec_id: SPEC-AUTH-0001
namespace: auth
type: feature
status: draft
</spec_header>

<summary>
Add a login endpoint that accepts email and password and returns a JWT token.
</summary>

<requirements>
functional:
  - id: FR-1
    description: User can log in with email and password
    priority: must-have
  - id: FR-2
    description: System returns a JWT token on successful login
    priority: must-have
non_functional:
  - id: NFR-1
    description: Login endpoint responds within 500ms at p95
    priority: should-have
</requirements>

<technical_design>
affected_components:
  - auth/views.py
  - auth/serializers.py
api_changes:
  - method: POST
    path: /api/v1/auth/login
    description: Accept email and password, return JWT
data_model_changes: []
</technical_design>

<acceptance_criteria>
- [ ] AC-1: User can log in with valid credentials and receives a JWT
- [ ] AC-2: Invalid credentials return 401
- [ ] AC-3: Response time is under 500ms at p95
</acceptance_criteria>

Follow this EXACT format. Output ONLY the XML tags with YAML content inside."""

SPEC_GENERATION_PROMPT = """Generate a specification for:

USER REQUEST: {user_request}

Use these values in the spec_header:
- format_version: 2
- spec_id: {spec_id}
- namespace: {namespace}
- type: {spec_type}
- status: draft

{related_specs_context}

{stack_config_context}

{revision_context}

Output ONLY the XML specification with these sections: spec_header, summary, requirements, technical_design, acceptance_criteria.
Do NOT wrap in markdown code fences. Start directly with <spec_header>."""


def spec_generator_agent(state: WorkflowState) -> dict:
    """Generate a new specification or revise based on feedback."""
    user_request = state["user_request"]
    namespaces = state.get("identified_namespaces", [])
    classification = state.get("request_classification", "new")
    related_specs = state.get("related_specs", [])
    revision_count = state.get("spec_revision_count", 0)
    rejection_feedback = state.get("spec_rejection_feedback", "")
    validation_results = state.get("spec_validation_results", [])
    existing_spec_id = state.get("spec_id", "")

    logger.info(
        "spec_generator_start",
        classification=classification,
        revision=revision_count,
        namespace_count=len(namespaces),
    )

    from src.graph.workflow import notify_sub_step
    workflow_id = state.get("workflow_id", "")

    try:
        # Resolve namespace and allocate spec_id
        notify_sub_step(workflow_id, "spec_generator", "Template Selection",
                        detail=f"Classification: {classification}, namespace: {namespaces[0] if namespaces else 'general'}"
                               + (f", revision #{revision_count}" if revision_count > 0 else ""))
        namespace = _resolve_primary_namespace(namespaces)
        ns_obj = Namespace.objects.filter(name=namespace).first()
        notify_sub_step(workflow_id, "spec_generator", "Template Selection",
                        detail=f"Resolved namespace: {namespace}" + (f" (stack: {ns_obj.stack_config.get('language', '?')}/{ns_obj.stack_config.get('framework', '?')})" if ns_obj and ns_obj.stack_config else ""))

        if existing_spec_id and revision_count > 0:
            spec_id = existing_spec_id
        elif ns_obj:
            spec_id = ns_obj.allocate_spec_id()
        else:
            spec_id = f"SPEC-GENERAL-0001"

        # Build stack config context
        stack_config_context = ""
        if ns_obj and ns_obj.stack_config:
            sc = ns_obj.stack_config
            stack_config_context = f"""STACK CONFIG (from namespace):
language: {sc.get('language', 'python')}
framework: {sc.get('framework', 'django')}
test_framework: {sc.get('test_framework', 'pytest')}
build_tool: {sc.get('build_tool', 'pip')}"""

        # Build related specs context
        related_specs_context = ""
        if related_specs:
            parts = []
            for rs in related_specs[:3]:  # Limit to top 3
                parts.append(
                    f"--- {rs['spec_id']} (score: {rs['score']:.2f}) ---\n{rs['content'][:2000]}"
                )
            related_specs_context = (
                "RELATED EXISTING SPECS (for context, avoid contradictions):\n"
                + "\n\n".join(parts)
            )

        # Build revision context
        revision_context = ""
        if revision_count > 0 and rejection_feedback:
            revision_context = f"""REVISION #{revision_count}:
The previous spec was rejected with the following feedback:
{rejection_feedback}

Please regenerate the spec incorporating this feedback."""
        elif revision_count > 0 and validation_results:
            failed = [r for r in validation_results if not r["is_valid"]]
            if failed:
                errors = "\n".join(f"- {r['check']}: {r['message']}" for r in failed)
                revision_context = f"""REVISION #{revision_count}:
The previous spec failed validation with these errors:
{errors}

Please fix these issues in the regenerated spec."""

        # Template based on classification
        template_map = {
            "new": "feature",
            "bugfix": "bugfix",
            "update": "change-request",
        }
        template = template_map.get(classification, "feature")

        notify_sub_step(workflow_id, "spec_generator", "Template Selection",
                        detail=f"Allocated {spec_id} — using '{template}' template")

        # Generate spec via LLM
        notify_sub_step(workflow_id, "spec_generator", "LLM Spec Generation",
                        detail=f"Building prompt with {len(related_specs)} related spec(s) as context...")
        prompt = SPEC_GENERATION_PROMPT.format(
            user_request=user_request,
            namespace=namespace,
            spec_type=template,
            spec_id=spec_id,
            related_specs_context=related_specs_context,
            stack_config_context=stack_config_context,
            revision_context=revision_context,
            template=template,
        )

        notify_sub_step(workflow_id, "spec_generator", "LLM Spec Generation",
                        detail=f"Calling LLM to generate {spec_id} (prompt: {len(prompt)} chars, max_tokens: 4096)...")
        response = call_llm(
            prompt=prompt,
            system_prompt=SPEC_GENERATION_SYSTEM_PROMPT,
            agent_name="spec_generation",
            max_tokens=4096,
            temperature=0.3,
        )

        generated_spec = response.content.strip()
        notify_sub_step(workflow_id, "spec_generator", "LLM Spec Generation",
                        detail=f"LLM returned {len(generated_spec)} chars of XML spec content")

        # Detect low confidence sections (simple heuristic)
        low_confidence = _detect_low_confidence(generated_spec)
        if low_confidence:
            notify_sub_step(workflow_id, "spec_generator", "LLM Spec Generation",
                            detail=f"Detected {len(low_confidence)} low-confidence section(s): {', '.join(lc[:40] for lc in low_confidence[:3])}")

        # Sub-agent: Consistency Checker — compare against existing specs
        notify_sub_step(workflow_id, "spec_generator", "Consistency Check (Qdrant)", spec_id=spec_id,
                        detail=f"Sending {spec_id} to consistency checker (comparing against {len(related_specs)} related spec(s))...")
        consistency_result = check_consistency(
            generated_spec=generated_spec,
            spec_id=spec_id,
            namespace=namespace,
            related_specs=related_specs,
        )
        warnings_count = len(consistency_result.get("consistency_warnings", []))
        has_dup = bool(consistency_result.get("duplicate_warning"))
        notify_sub_step(workflow_id, "spec_generator", "Consistency Check (Qdrant)", spec_id=spec_id,
                        detail=f"Result: {warnings_count} warning(s), duplicate={'yes' if has_dup else 'no'}")

        # Merge duplicate_warning: discovery may have set one, consistency checker may override
        duplicate_warning = state.get("duplicate_warning")
        if consistency_result.get("duplicate_warning"):
            duplicate_warning = consistency_result["duplicate_warning"]

        logger.info(
            "spec_generator_complete",
            spec_id=spec_id,
            spec_length=len(generated_spec),
            low_confidence_count=len(low_confidence),
            consistency_warnings=len(consistency_result.get("consistency_warnings", [])),
        )

        return {
            "generated_spec": generated_spec,
            "spec_id": spec_id,
            "low_confidence_sections": low_confidence,
            "consistency_warnings": consistency_result.get("consistency_warnings", []),
            "duplicate_warning": duplicate_warning,
            "current_agent": "spec_generator",
        }

    except Exception as e:
        logger.error("spec_generator_error", error=str(e))
        return {
            "generated_spec": "",
            "spec_id": "",
            "low_confidence_sections": [],
            "current_agent": "spec_generator",
            "error": f"Spec generation failed: {str(e)}",
        }


def _resolve_primary_namespace(namespaces: list[str]) -> str:
    """Pick the primary namespace or default to 'general'."""
    if namespaces:
        return namespaces[0]
    # Fallback: create 'general' namespace if none found
    ns, _ = Namespace.objects.get_or_create(
        name="general",
        defaults={
            "description": "General specifications",
            "stack_config": {
                "language": "python",
                "framework": "django",
                "test_framework": "pytest",
                "build_tool": "pip",
            },
        },
    )
    return ns.name


def _detect_low_confidence(spec_content: str) -> list[str]:
    """Simple heuristic to detect sections the LLM might be unsure about."""
    low_confidence = []
    indicators = ["TBD", "TODO", "estimated", "approximate", "to be determined", "placeholder"]
    lines = spec_content.split("\n")
    for line in lines:
        for indicator in indicators:
            if indicator.lower() in line.lower():
                low_confidence.append(line.strip()[:100])
                break
    return low_confidence
