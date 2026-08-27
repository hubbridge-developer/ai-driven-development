"""Task Planner — decomposes spec into ordered implementation tasks."""

import json
import structlog
from src.llm.provider import call_llm

logger = structlog.get_logger()

TASK_PLANNER_PROMPT = """You are a senior software engineer decomposing a specification into implementation tasks.

SPECIFICATION:
{spec_content}

REPOSITORY STRUCTURE (the ACTUAL files/folders in the target repo):
{repo_context}

AFFECTED FILES:
{affected_files}

STACK: {stack_config}
{rejection_feedback}
Break this specification into ordered implementation tasks. CRITICAL rules:
1. Use ONLY directories/apps that already appear in the REPOSITORY STRUCTURE
   above. Do NOT invent a new app or folder named after the domain — put new
   files inside the EXISTING app directory shown in the file tree (e.g. if the
   tree shows `accounts/`, use `accounts/`, never a made-up `auth/`).
2. To expose a NEW URL route, register it in the project's EXISTING root URLconf
   from the file tree (the `<project>/urls.py` that includes the app urls), so
   the route is actually reachable — a route added only to an app's urls that is
   not included will 404.
3. Put tests in the same app's existing test location shown in the tree.
4. Use the FEWEST tasks possible. A simple endpoint is usually 1–2 tasks, not 5.
   Do not split trivial work into separate tasks.
5. Order by dependency (models before views, views before urls).

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
               stack_config: dict, rejection_feedback: str = "",
               repo_context: str = "") -> list[dict]:
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
        repo_context=(repo_context or "(no repository structure available)")[:2500],
        affected_files=af_str or "(none — this is likely a NEW feature; add files to the existing app)",
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
