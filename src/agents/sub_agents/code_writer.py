"""Code Writer — generates code for each implementation task via LLM."""

import json
import re
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
    """Parse LLM response for generated files, tolerating common weak-model quirks.

    Staged fallbacks (each more lenient than the last):
      1. strict JSON
      2. JSON of the outermost {...} substring (ignores prose around it)
      3. coerce Python triple-quoted content ( \"\"\"...\"\"\" ) into valid JSON strings
      4. regex salvage of each {path, action, content, language} object
    """
    text = content.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # 1) strict
    files = _files_from_json(text)
    if files is not None:
        return files

    # narrow to the outermost object
    start, end = text.find("{"), text.rfind("}") + 1
    if 0 <= start < end:
        blob = text[start:end]
        # 2) plain JSON of the object
        files = _files_from_json(blob)
        if files is not None:
            return files
        # 3) triple-quoted content -> escaped JSON string, then retry
        files = _files_from_json(_coerce_triple_quoted(blob))
        if files is not None:
            return files
        # 4) last resort: regex-extract each file
        files = _salvage_files(blob)
        if files:
            logger.info("code_writer_parse_salvaged", files=len(files))
            return files

    logger.warning("code_writer_parse_failed", content=content[:200])
    return []


def _files_from_json(text: str):
    """Return the 'files' list if `text` is valid JSON with one, else None."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    return files if isinstance(files, list) else None


def _coerce_triple_quoted(text: str) -> str:
    """Rewrite  <key>: \"\"\"...\"\"\"  as a properly escaped JSON string.

    The closing \"\"\" must be followed by a comma or a closing brace, so a
    docstring's \"\"\" *inside* the code (typically followed by a newline) does
    not prematurely end the match.
    """
    pattern = re.compile(r':\s*"""(.*?)"""\s*(?=[,}])', re.DOTALL)
    return pattern.sub(lambda m: ": " + json.dumps(m.group(1)), text)


def _salvage_files(blob: str) -> list[dict]:
    """Best-effort extraction of file objects when JSON parsing fails outright."""
    files = []
    for m in re.finditer(r'"path"\s*:\s*"([^"]+)"', blob):
        path = m.group(1)
        seg = blob[m.end():m.end() + 200000]
        action = _first_group(r'"action"\s*:\s*"([^"]+)"', seg) or "modify"
        language = _first_group(r'"language"\s*:\s*"([^"]+)"', seg) or "python"

        # content as a triple-quoted block, else a JSON string up to the next key/brace
        content = _first_group(r'"content"\s*:\s*"""(.*?)"""\s*(?=[,}]|\s*")', seg, re.DOTALL)
        if content is None:
            raw = _first_group(r'"content"\s*:\s*"(.*?)"\s*(?=,\s*"|\s*[}\]])', seg, re.DOTALL)
            if raw is not None:
                try:
                    content = json.loads('"' + raw + '"')
                except (json.JSONDecodeError, ValueError):
                    content = raw.encode("utf-8").decode("unicode_escape", "ignore")
        if content:
            files.append({"path": path, "action": action, "content": content, "language": language})
    return files


def _first_group(pattern: str, text: str, flags: int = 0):
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None
