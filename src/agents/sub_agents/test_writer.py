"""Test Writer — generates unit and integration tests from acceptance criteria."""

import json
import structlog
from src.llm.provider import call_llm

logger = structlog.get_logger()

TEST_WRITER_PROMPT = """You are an expert test engineer writing tests using {test_framework}.

SPECIFICATION (acceptance criteria):
{acceptance_criteria}

GENERATED CODE FILES:
{generated_files_summary}

STACK: {language} / {framework} / {test_framework}
{failure_feedback}
Write comprehensive tests that verify all acceptance criteria. Return ONLY a JSON object:
{{
  "tests": [
    {{
      "path": "accounts/tests/test_password_reset.py",
      "content": "full test file content...",
      "test_type": "unit"
    }}
  ]
}}

IMPORTANT:
- Cover each acceptance criterion with at least one test
- Include both happy path and error cases
- Use {test_framework} conventions
- Import from the actual code files listed above
- test_type should be "unit" or "integration"
- Do NOT include markdown fences, only the JSON object
"""


def write_tests(spec_content: str, generated_files: list[dict],
                stack_config: dict, failure_feedback: str = "") -> list[dict]:
    """Generate tests based on acceptance criteria and generated code.

    failure_feedback: output of a previous run where the TEST file itself was
    broken (missing imports etc.) — instructs the LLM to fix the test code.

    Returns list of {path, content, test_type} dicts.
    """
    logger.info("test_writer_start", generated_files=len(generated_files))

    language = stack_config.get("language", "python")
    framework = stack_config.get("framework", "django")
    test_framework = stack_config.get("test_framework", "pytest")

    # Extract acceptance criteria from spec
    import re
    ac_match = re.search(r"<acceptance_criteria>(.*?)</acceptance_criteria>", spec_content, re.DOTALL)
    acceptance_criteria = ac_match.group(1).strip() if ac_match else spec_content[:1500]

    # Summarize generated files (path + first few lines)
    files_summary = ""
    for f in generated_files:
        content_preview = f.get("content", "")[:500]
        files_summary += f"\n--- {f['path']} ({f.get('action', 'create')}) ---\n{content_preview}\n"

    feedback_section = ""
    if failure_feedback:
        feedback_section = (
            "\nYOUR PREVIOUS TEST FILE FAILED TO RUN — the failure was in the TEST CODE "
            "itself (missing imports, undefined names, wrong references). Fix the test "
            "file. Include ALL required imports. Failure output:\n"
            f"{failure_feedback}\n"
        )

    prompt = TEST_WRITER_PROMPT.format(
        test_framework=test_framework,
        acceptance_criteria=acceptance_criteria,
        generated_files_summary=files_summary[:3000],
        language=language,
        framework=framework,
        failure_feedback=feedback_section,
    )

    try:
        response = call_llm(prompt, agent_name="code_developer", max_tokens=4096)
        tests = _parse_test_response(response.content)
        logger.info("test_writer_complete", tests_generated=len(tests))
        return tests
    except Exception as e:
        logger.error("test_writer_failed", error=str(e))
        return []


def _parse_test_response(content: str) -> list[dict]:
    """Parse LLM response for test files."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return data.get("tests", [])
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                return data.get("tests", [])
            except json.JSONDecodeError:
                pass

    logger.warning("test_writer_parse_failed", content=content[:200])
    return []
