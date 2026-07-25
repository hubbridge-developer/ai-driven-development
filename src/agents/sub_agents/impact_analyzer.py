"""Impact Analyzer — LLM-based analysis of which files need modification/creation."""

import json
import structlog
from src.llm.provider import call_llm

logger = structlog.get_logger()

IMPACT_ANALYSIS_PROMPT = """You are a senior software engineer analyzing a specification to determine which files need to be created or modified.

SPECIFICATION:
{spec_content}

REPOSITORY FILE TREE:
{file_tree}

DEPENDENCIES:
{dependency_map}

STACK:
{stack_config}

Based on the specification requirements, identify which files need to be:
1. CREATED (new files that don't exist yet)
2. MODIFIED (existing files that need changes)

For each file, explain WHY it needs to be changed.

Respond in JSON format ONLY:
{{
  "affected_files": [
    {{"path": "accounts/views.py", "action": "modify", "reason": "Add password reset view"}},
    {{"path": "accounts/tokens.py", "action": "create", "reason": "Token generation for email verification"}}
  ],
  "impact_summary": "Brief 2-3 sentence summary of the overall impact and blast radius"
}}
"""


def analyze_impact(spec_content: str, file_tree: list[str], dependency_map: dict,
                   stack_config: dict) -> tuple[list[dict], str]:
    """Analyze spec against repo structure to identify affected files.

    Returns: (affected_files, impact_summary)
    """
    logger.info("impact_analysis_start", file_count=len(file_tree))

    # Truncate file tree for prompt
    tree_str = "\n".join(file_tree[:100])
    deps_str = "\n".join(f"{k}: {v}" for k, v in list(dependency_map.items())[:30])
    stack_str = json.dumps(stack_config)

    prompt = IMPACT_ANALYSIS_PROMPT.format(
        spec_content=spec_content[:3000],
        file_tree=tree_str,
        dependency_map=deps_str,
        stack_config=stack_str,
    )

    try:
        response = call_llm(prompt, agent_name="namespace_resolver")
        result = _parse_impact_response(response.content)

        affected_files = result.get("affected_files", [])
        impact_summary = result.get("impact_summary", "Impact analysis completed.")

        logger.info("impact_analysis_complete", affected_files=len(affected_files))
        return affected_files, impact_summary

    except Exception as e:
        logger.error("impact_analysis_failed", error=str(e))
        # Fallback: return empty results
        return [], f"Impact analysis failed: {str(e)}"


def _parse_impact_response(content: str) -> dict:
    """Parse LLM response, extracting JSON from potential markdown wrapping."""
    # Strip markdown code fences
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    logger.warning("impact_parse_failed", content=content[:200])
    return {"affected_files": [], "impact_summary": "Could not parse impact analysis."}
