"""Lint Formatter — deterministic code cleanup (ruff autofix + format)."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger()


def lint_and_format(generated_files: list[dict], generated_tests: list[dict],
                    stack_config: dict) -> list[dict]:
    """Apply formatting and lint fixes to generated code.

    Python files are cleaned with ruff (`check --fix-only` + `format`) when
    ruff is installed; everything gets basic cleanup (trailing whitespace,
    EOF newline). Deterministic — an LLM pass here could silently corrupt
    code with no diff to review.

    Returns the final cleaned list of all files (code + tests merged).
    """
    all_files = generated_files + [
        {"path": t["path"], "action": "create", "content": t["content"],
         "language": stack_config.get("language", "python")}
        for t in generated_tests
    ]

    if not all_files:
        return []

    logger.info("lint_format_start", files=len(all_files))

    cleaned = _basic_cleanup(all_files)

    if shutil.which("ruff"):
        cleaned = _ruff_clean(cleaned)
    else:
        logger.info("lint_format_ruff_unavailable")

    logger.info("lint_format_complete", files=len(cleaned))
    return cleaned


def _ruff_clean(files: list[dict]) -> list[dict]:
    """Run ruff autofix + formatter on Python files via a temp workspace."""
    if not any(f["path"].endswith(".py") for f in files):
        return files

    with tempfile.TemporaryDirectory(prefix="add-lint-") as tmp:
        root = Path(tmp)
        written = []
        for f in files:
            if not f["path"].endswith(".py"):
                continue
            target = (root / f["path"]).resolve()
            if root.resolve() not in target.parents:
                logger.warning("lint_format_path_skipped", path=f["path"])
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.get("content", ""), encoding="utf-8")
            written.append(f["path"])

        for cmd in (["ruff", "check", "--fix-only", "--quiet", "."],
                    ["ruff", "format", "--quiet", "."]):
            try:
                subprocess.run(cmd, cwd=root, capture_output=True, timeout=60)
            except Exception as e:
                logger.warning("lint_format_ruff_failed", cmd=cmd[1], error=str(e))
                return files

        result = []
        for f in files:
            if f["path"] in written:
                content = (root / f["path"]).read_text(encoding="utf-8")
                result.append({**f, "content": content})
            else:
                result.append(f)
        return result


def _basic_cleanup(files: list[dict]) -> list[dict]:
    """Basic cleanup — fix trailing whitespace, ensure newline at EOF."""
    cleaned = []
    for f in files:
        content = f.get("content", "")
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in content.splitlines()]
        content = "\n".join(lines)
        # Ensure trailing newline
        if not content.endswith("\n"):
            content += "\n"
        cleaned.append({
            "path": f["path"],
            "action": f.get("action", "create"),
            "content": content,
            "language": f.get("language", "python"),
        })
    return cleaned
