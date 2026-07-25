"""Integration Checker — validates cross-file consistency of generated code."""

import json
import structlog
from src.llm.provider import call_llm

logger = structlog.get_logger()

INTEGRATION_CHECK_PROMPT = """You are a senior code reviewer checking cross-file consistency.

Review ALL the generated files and tests below for consistency issues:

GENERATED FILES:
{files_content}

GENERATED TESTS:
{tests_content}

Check for:
1. Import paths that don't resolve to actual files
2. Function signatures that don't match call sites
3. Missing model fields referenced in serializers/views
4. Test imports that reference non-existent classes/functions
5. Circular dependencies between modules

Return ONLY a JSON object:
{{
  "issues": [
    {{
      "severity": "critical",
      "file": "accounts/views.py",
      "description": "Imports PasswordResetToken from models.py but it's not defined there"
    }}
  ]
}}

severity must be "critical" or "warning". If no issues found, return {{"issues": []}}
Do NOT include markdown fences, only the JSON object.
"""


def check_integration(generated_files: list[dict], generated_tests: list[dict]) -> list[dict]:
    """Validate cross-file consistency of generated code.

    Returns list of {severity, file, description} dicts.
    """
    logger.info("integration_check_start",
                files=len(generated_files), tests=len(generated_tests))

    # Build content summaries
    files_content = ""
    for f in generated_files:
        files_content += f"\n--- {f['path']} ---\n{f.get('content', '')}\n"

    tests_content = ""
    for t in generated_tests:
        tests_content += f"\n--- {t['path']} ---\n{t.get('content', '')}\n"

    # Truncate if too long
    files_content = files_content[:4000]
    tests_content = tests_content[:2000]

    prompt = INTEGRATION_CHECK_PROMPT.format(
        files_content=files_content,
        tests_content=tests_content,
    )

    try:
        response = call_llm(prompt, agent_name="code_developer", max_tokens=2048)
        issues = _parse_issues(response.content)
        logger.info("integration_check_complete", issues=len(issues))
        return issues
    except Exception as e:
        logger.error("integration_check_failed", error=str(e))
        return []


def _parse_issues(content: str) -> list[dict]:
    """Parse LLM response for integration issues."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return data.get("issues", [])
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                return data.get("issues", [])
            except json.JSONDecodeError:
                pass
    return []
