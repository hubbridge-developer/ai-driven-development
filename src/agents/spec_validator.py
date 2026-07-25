"""Agent 2.5 — Spec Validator: deterministic structural validation (no LLM)."""

import re
import structlog
import yaml
from src.graph.state import WorkflowState, ValidationResult

logger = structlog.get_logger()

REQUIRED_SECTIONS = {"spec_header", "summary", "requirements", "technical_design", "acceptance_criteria"}
REQUIRED_HEADER_FIELDS = {"format_version", "spec_id", "namespace", "type"}
EXPECTED_FORMAT_VERSION = 2


def spec_validator_agent(state: WorkflowState) -> dict:
    """Validate spec structure — deterministic, no LLM needed."""
    generated_spec = state.get("generated_spec", "")
    retry_count = state.get("spec_validation_retry_count", 0)

    # Clean up common LLM output artifacts
    generated_spec = _clean_spec_output(generated_spec)
    state_update = {"generated_spec": generated_spec}

    logger.info("spec_validator_start", spec_length=len(generated_spec), retry=retry_count)

    from src.graph.workflow import notify_sub_step
    workflow_id = state.get("workflow_id", "")

    results: list[ValidationResult] = []

    # Check 1: XML Well-formedness
    notify_sub_step(workflow_id, "spec_validator", "XML Well-formedness",
                    detail="Scanning XML tags for proper open/close pairing...")
    r1 = _check_xml_wellformedness(generated_spec)
    results.append(r1)
    notify_sub_step(workflow_id, "spec_validator", "XML Well-formedness",
                    detail=f"{'PASS' if r1['is_valid'] else 'FAIL'}: {r1['message']}")

    # Check 2: Required sections present
    notify_sub_step(workflow_id, "spec_validator", "Required Sections Check",
                    detail=f"Looking for {len(REQUIRED_SECTIONS)} sections: {', '.join(sorted(REQUIRED_SECTIONS))}")
    r2 = _check_required_sections(generated_spec)
    results.append(r2)
    notify_sub_step(workflow_id, "spec_validator", "Required Sections Check",
                    detail=f"{'PASS' if r2['is_valid'] else 'FAIL'}: {r2['message']}")

    # Check 3: Required header fields
    notify_sub_step(workflow_id, "spec_validator", "Header Fields Check",
                    detail=f"Parsing spec_header YAML, checking for: {', '.join(sorted(REQUIRED_HEADER_FIELDS))}")
    r3 = _check_required_fields(generated_spec)
    results.append(r3)
    notify_sub_step(workflow_id, "spec_validator", "Header Fields Check",
                    detail=f"{'PASS' if r3['is_valid'] else 'FAIL'}: {r3['message']}")

    # Check 4: Format version
    notify_sub_step(workflow_id, "spec_validator", "Format Version Match",
                    detail=f"Checking format_version == {EXPECTED_FORMAT_VERSION}")
    r4 = _check_format_version(generated_spec)
    results.append(r4)
    notify_sub_step(workflow_id, "spec_validator", "Format Version Match",
                    detail=f"{'PASS' if r4['is_valid'] else 'FAIL'}: {r4['message']}")

    # Check 5: Cross-references (non-blocking warning)
    notify_sub_step(workflow_id, "spec_validator", "Cross-reference Validation",
                    detail="Checking dependency spec IDs exist in database...")
    r5 = _check_cross_references(generated_spec)
    results.append(r5)
    notify_sub_step(workflow_id, "spec_validator", "Cross-reference Validation",
                    detail=f"{'PASS' if r5['is_valid'] else 'WARN'}: {r5['message']}")

    all_valid = all(r["is_valid"] for r in results)
    passed = sum(1 for r in results if r["is_valid"])
    notify_sub_step(workflow_id, "spec_validator", "Cross-reference Validation",
                    detail=f"Validation complete: {passed}/{len(results)} checks passed" + (" — will retry" if not all_valid and retry_count < 2 else ""))

    # If invalid, increment retry count
    new_retry_count = retry_count
    if not all_valid:
        new_retry_count = retry_count + 1

    logger.info(
        "spec_validator_complete",
        all_valid=all_valid,
        retry_count=new_retry_count,
        checks=[{"check": r["check"], "valid": r["is_valid"]} for r in results],
    )

    return {
        **state_update,
        "spec_validation_results": results,
        "spec_validation_retry_count": new_retry_count,
        "spec_format_version": EXPECTED_FORMAT_VERSION if all_valid else 0,
        "current_agent": "spec_validator",
    }


def _check_xml_wellformedness(spec: str) -> ValidationResult:
    """Check that all XML tags are properly opened and closed."""
    tag_pattern = re.compile(r"<(/?)(\w+)>")
    stack = []
    for match in tag_pattern.finditer(spec):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2)
        if is_closing:
            if not stack or stack[-1] != tag_name:
                return {
                    "check": "xml_wellformedness",
                    "is_valid": False,
                    "message": f"Mismatched closing tag </{tag_name}>. Expected </{stack[-1] if stack else 'none'}>",
                }
            stack.pop()
        else:
            stack.append(tag_name)

    if stack:
        return {
            "check": "xml_wellformedness",
            "is_valid": False,
            "message": f"Unclosed tags: {', '.join(stack)}",
        }

    return {"check": "xml_wellformedness", "is_valid": True, "message": "OK"}


def _check_required_sections(spec: str) -> ValidationResult:
    """Check that all required XML sections exist."""
    found_sections = set(re.findall(r"<(\w+)>", spec))
    missing = REQUIRED_SECTIONS - found_sections

    if missing:
        return {
            "check": "required_sections",
            "is_valid": False,
            "message": f"Missing required sections: {', '.join(sorted(missing))}",
        }

    return {"check": "required_sections", "is_valid": True, "message": "OK"}


def _check_required_fields(spec: str) -> ValidationResult:
    """Check that spec_header contains all required fields."""
    header_match = re.search(r"<spec_header>(.*?)</spec_header>", spec, re.DOTALL)
    if not header_match:
        return {
            "check": "required_fields",
            "is_valid": False,
            "message": "No spec_header section found",
        }

    header_text = header_match.group(1).strip()
    try:
        header = yaml.safe_load(header_text)
        if not isinstance(header, dict):
            return {
                "check": "required_fields",
                "is_valid": False,
                "message": "spec_header is not valid YAML",
            }
    except yaml.YAMLError as e:
        return {
            "check": "required_fields",
            "is_valid": False,
            "message": f"spec_header YAML parse error: {str(e)[:100]}",
        }

    missing_fields = [f for f in REQUIRED_HEADER_FIELDS if not header.get(f)]
    if missing_fields:
        return {
            "check": "required_fields",
            "is_valid": False,
            "message": f"Missing header fields: {', '.join(missing_fields)}",
        }

    return {"check": "required_fields", "is_valid": True, "message": "OK"}


def _check_format_version(spec: str) -> ValidationResult:
    """Check that format_version matches expected version."""
    header_match = re.search(r"<spec_header>(.*?)</spec_header>", spec, re.DOTALL)
    if not header_match:
        return {
            "check": "format_version",
            "is_valid": False,
            "message": "No spec_header found",
        }

    try:
        header = yaml.safe_load(header_match.group(1).strip())
        version = header.get("format_version")
        if version != EXPECTED_FORMAT_VERSION:
            return {
                "check": "format_version",
                "is_valid": False,
                "message": f"Expected format_version {EXPECTED_FORMAT_VERSION}, got {version}",
            }
    except Exception:
        return {
            "check": "format_version",
            "is_valid": False,
            "message": "Could not parse format_version",
        }

    return {"check": "format_version", "is_valid": True, "message": "OK"}


def _check_cross_references(spec: str) -> ValidationResult:
    """Check dependency cross-references — always passes (warning only)."""
    deps_match = re.search(r"<dependencies>(.*?)</dependencies>", spec, re.DOTALL)
    if not deps_match:
        return {"check": "cross_references", "is_valid": True, "message": "No dependencies section"}

    # Extract spec IDs referenced
    spec_ids = re.findall(r"SPEC-\w+-\d+", deps_match.group(1))
    if spec_ids:
        from src.aidd_api.models import GeneratedSpec

        existing = set(
            GeneratedSpec.objects.filter(spec_id__in=spec_ids)
            .values_list("spec_id", flat=True)
        )
        missing = set(spec_ids) - existing
        if missing:
            return {
                "check": "cross_references",
                "is_valid": True,  # Non-blocking
                "message": f"Warning: referenced specs not found: {', '.join(missing)}",
            }

    return {"check": "cross_references", "is_valid": True, "message": "OK"}


def _clean_spec_output(spec: str) -> str:
    """Strip common LLM artifacts: markdown fences, preamble text, trailing text."""
    import re

    # Remove markdown code fences
    spec = re.sub(r"```(?:xml|yaml|text)?\s*\n?", "", spec)
    spec = spec.replace("```", "")

    # Find the first <spec_header> and last closing tag — keep only that
    start = spec.find("<spec_header>")
    if start == -1:
        return spec.strip()

    # Find the last closing XML tag
    last_close = -1
    for tag in ["</dependencies>", "</acceptance_criteria>", "</technical_design>",
                "</requirements>", "</summary>", "</background>", "</spec_header>"]:
        idx = spec.rfind(tag)
        if idx != -1:
            end = idx + len(tag)
            if end > last_close:
                last_close = end

    if last_close > start:
        spec = spec[start:last_close]

    return spec.strip()
