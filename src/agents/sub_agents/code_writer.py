"""Code Writer — generates code for each implementation task via LLM."""

import json
import base64
import structlog
import requests
from src.llm.provider import call_llm
from src.github.service import _headers, GITHUB_API

logger = structlog.get_logger()

CODE_WRITER_PROMPT = """You are an expert {language} developer using {framework}.

TASK: {task_description}

SPECIFICATION CONTEXT:
{spec_context}

CODE CONTEXT:
{code_context}

{existing_file_section}

Write the code for this task. Return ONLY a JSON object with the files to create or modify:
{{
  "files": [
    {{
      "path": "accounts/models.py",
      "action": "modify",
      "content": "full file content here...",
      "language": "python"
    }}
  ]
}}

IMPORTANT:
- For "modify" actions, return the COMPLETE updated file content (not just the diff)
- CRITICAL: when modifying a file you MUST preserve ALL existing functions, classes,
  imports, and URL routes shown in the EXISTING FILE section — add your changes to
  them. Deleting or omitting existing code is a failure.
- For "create" actions, return the complete new file
- Follow {framework} conventions and best practices
- Include proper imports
- Do NOT include markdown fences in your response, only the JSON object
"""


def write_code(task: dict, spec_content: str, code_context: str,
               stack_config: dict, target_repo: dict) -> list[dict]:
    """Generate code for a single implementation task.

    Returns list of {path, action, content, language} dicts.
    """
    logger.info("code_writer_start", task_id=task.get("task_id"), files=task.get("files", []))

    language = stack_config.get("language", "python")
    framework = stack_config.get("framework", "django")

    # Fetch existing file content for modify actions
    from django.conf import settings
    existing_section = ""
    for file_path in task.get("files", []):
        content = _fetch_file_content(
            target_repo["owner"], target_repo["repo"],
            target_repo["branch"], file_path, settings.GITHUB_PAT
        )
        if content:
            existing_section += f"\nEXISTING FILE ({file_path}):\n```\n{content}\n```\n"

    if not existing_section:
        existing_section = "(No existing files — all files are new)"

    prompt = CODE_WRITER_PROMPT.format(
        language=language,
        framework=framework,
        task_description=task.get("description", ""),
        spec_context=spec_content[:2000],
        code_context=code_context[:2000],
        existing_file_section=existing_section,
    )

    try:
        response = call_llm(prompt, agent_name="code_developer", max_tokens=4096)
        files = _parse_code_response(response.content)
        logger.info("code_writer_complete", task_id=task.get("task_id"), files_generated=len(files))
        return files
    except Exception as e:
        logger.error("code_writer_failed", task_id=task.get("task_id"), error=str(e))
        return []


def _fetch_file_content(owner: str, repo: str, branch: str, path: str, token: str) -> str:
    """Fetch file content from GitHub."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if resp.status_code == 200:
        return base64.b64decode(resp.json()["content"]).decode("utf-8")
    return ""


def _parse_code_response(content: str) -> list[dict]:
    """Parse LLM response for generated files."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return data.get("files", [])
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                return data.get("files", [])
            except json.JSONDecodeError:
                pass

    logger.warning("code_writer_parse_failed", content=content[:200])
    return []
