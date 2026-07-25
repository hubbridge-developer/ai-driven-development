"""Task Planner — decomposes spec into ordered implementation tasks."""

import json
import structlog
from src.llm.provider import call_llm

logger = structlog.get_logger()

TASK_PLANNER_PROMPT = """You are a senior software engineer decomposing a specification into implementation tasks.

SPECIFICATION:
{spec_content}

AFFECTED FILES:
{affected_files}

STACK: {stack_config}
{rejection_feedback}
Break this specification into ordered implementation tasks. Each task should:
1. Map to specific files (create or modify)
2. Have clear dependencies (models before views, etc.)
3. Be small enough for a single focused code change

Respond in JSON format ONLY:
{{
  "tasks": [
    {{
      "task_id": "T1",
      "description": "Create PasswordResetToken model",
      "files": ["accounts/models.py"],
      "depends_on": []
    }},
    {{
      "task_id": "T2",
      "description": "Add password reset serializers",
      "files": ["accounts/serializers.py"],
      "depends_on": ["T1"]
    }}
  ]
}}
"""


def plan_tasks(spec_content: str, affected_files: list[dict],
               stack_config: dict, rejection_feedback: str = "") -> list[dict]:
    """Decompose spec into ordered implementation tasks."""
    logger.info("task_planner_start", affected_files=len(affected_files))

    af_str = "\n".join(
        f"[{f.get('action', '?')}] {f.get('path', '?')} — {f.get('reason', '')}"
        for f in affected_files
    )

    feedback_section = ""
    if rejection_feedback:
        feedback_section = (
            "\nREVIEWER FEEDBACK ON PREVIOUS IMPLEMENTATION "
            "(the task breakdown must address this):\n"
            f"{rejection_feedback}\n"
        )

    prompt = TASK_PLANNER_PROMPT.format(
        spec_content=spec_content[:3000],
        affected_files=af_str,
        stack_config=json.dumps(stack_config),
        rejection_feedback=feedback_section,
    )

    try:
        response = call_llm(prompt, agent_name="code_developer")
        result = _parse_tasks(response.content)
        tasks = result.get("tasks", [])
        logger.info("task_planner_complete", tasks=len(tasks))
        return tasks
    except Exception as e:
        logger.error("task_planner_failed", error=str(e))
        return []


def _parse_tasks(content: str) -> dict:
    """Parse LLM response for task list."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {"tasks": []}
