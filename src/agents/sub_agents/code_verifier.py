"""Code Verifier — deterministic syntax checks and best-effort test execution."""

import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import requests
import structlog

from src.github.service import _headers, GITHUB_API

logger = structlog.get_logger()


def check_syntax(files: list[dict]) -> list[dict]:
    """Compile-check Python files without executing them.

    Returns issues in the same shape the integration checker uses, so syntax
    errors feed the existing critical-issue retry loop.
    """
    issues = []
    for f in files:
        path = f.get("path", "")
        if not path.endswith(".py"):
            continue
        try:
            compile(f.get("content", ""), path, "exec")
        except SyntaxError as e:
            issues.append({
                "severity": "critical",
                "file": path,
                "description": f"Syntax error at line {e.lineno}: {e.msg}",
            })
    logger.info("syntax_check_complete", files=len(files), errors=len(issues))
    return issues


_ROUTE_RE = re.compile(r"""(?:path|re_path)\(\s*['"]([^'"]*)['"]""")


def check_preservation(generated_files: list[dict], target_repo: dict) -> list[dict]:
    """Verify that "modify" actions preserve the original file's contents.

    LLMs asked to return "the complete updated file" often return only their
    new feature, silently deleting existing code. For each modified Python
    file, fetch the original from GitHub and require that its top-level
    functions/classes and URL route strings still exist in the replacement.
    Anything missing is a critical issue (feeds the retry loop).
    """
    from src.agents.sub_agents.code_writer import _fetch_file_content
    from django.conf import settings

    issues = []
    for f in generated_files:
        path = f.get("path", "")
        if f.get("action") != "modify" or not path.endswith(".py"):
            continue

        original = _fetch_file_content(
            target_repo["owner"], target_repo["repo"],
            target_repo.get("branch", "main"), path, settings.GITHUB_PAT,
        )
        if not original:
            continue  # file didn't exist upstream — nothing to preserve

        new_content = f.get("content", "")

        # Top-level function/class definitions must survive
        try:
            original_defs = {n.name for n in ast.iter_child_nodes(ast.parse(original))
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            new_defs = {n.name for n in ast.iter_child_nodes(ast.parse(new_content))
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        except SyntaxError:
            continue  # check_syntax already reports this as critical

        missing_defs = sorted(original_defs - new_defs)
        if missing_defs:
            issues.append({
                "severity": "critical",
                "file": path,
                "description": (
                    f"Modification REMOVED existing definitions: {', '.join(missing_defs)}. "
                    f"A modify action must return the complete file with ALL existing code "
                    f"preserved plus the new changes."
                ),
            })

        # URL route strings (urls.py-style files) must survive
        missing_routes = sorted(set(_ROUTE_RE.findall(original)) - set(_ROUTE_RE.findall(new_content)))
        if missing_routes:
            issues.append({
                "severity": "critical",
                "file": path,
                "description": (
                    f"Modification REMOVED existing URL routes: {', '.join(missing_routes)}. "
                    f"Existing urlpatterns entries must be preserved."
                ),
            })

    logger.info("preservation_check_complete", files=len(generated_files), issues=len(issues))
    return issues


def run_generated_tests(generated_files: list[dict], generated_tests: list[dict],
                        target_repo: dict, timeout: int) -> dict:
    """Run the generated tests with pytest against a temp overlay of the target repo.

    Downloads the target repo tarball, overlays the generated files and tests,
    and runs pytest in a subprocess. Best-effort: any environment problem is
    reported as status "error" and is non-fatal for the pipeline.

    Returns {status: passed|failed|error|skipped, exit_code?, summary}.
    """
    if not generated_tests:
        return {"status": "skipped", "summary": "No tests were generated."}
    test_paths = [t["path"] for t in generated_tests if t.get("path", "").endswith(".py")]
    if not test_paths:
        return {"status": "skipped", "summary": "Only Python test execution is supported."}

    tmp = tempfile.mkdtemp(prefix="add-testrun-")
    try:
        root = _download_repo(target_repo, Path(tmp))
        if root is None:
            return {"status": "error", "summary": "Could not download target repository."}

        for f in list(generated_files) + list(generated_tests):
            dest = (root / f.get("path", "")).resolve()
            if root.resolve() not in dest.parents:
                logger.warning("test_run_path_skipped", path=f.get("path", ""))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f.get("content", ""), encoding="utf-8")

        # Run in the target repo's context, not ADD's: drop the API
        # container's DJANGO_SETTINGS_MODULE and use the one declared in the
        # target repo's manage.py.
        env = os.environ.copy()
        env.pop("DJANGO_SETTINGS_MODULE", None)
        detected_settings = _detect_django_settings(root)
        if detected_settings:
            env["DJANGO_SETTINGS_MODULE"] = detected_settings
        env["PYTHONPATH"] = str(root)

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", *test_paths],
            cwd=root, capture_output=True, text=True, timeout=timeout, env=env,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        tail = "\n".join(output.splitlines()[-15:])
        if proc.returncode == 0:
            status = "passed"
        elif proc.returncode == 1:
            status = "failed"
        else:
            # 2-5: collection/usage/internal errors — environment, not the code
            status = "error"
        logger.info("test_run_complete", status=status, exit_code=proc.returncode)
        return {"status": status, "exit_code": proc.returncode, "summary": tail}

    except subprocess.TimeoutExpired:
        return {"status": "error", "summary": f"Test run timed out after {timeout}s."}
    except Exception as e:
        logger.error("test_run_failed", error=str(e))
        return {"status": "error", "summary": f"Test run failed: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _detect_django_settings(root: Path) -> str:
    """Read the DJANGO_SETTINGS_MODULE default from the target repo's manage.py."""
    manage = root / "manage.py"
    if not manage.exists():
        return ""
    try:
        m = re.search(
            r"DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([\w.]+)['\"]",
            manage.read_text(encoding="utf-8"),
        )
        return m.group(1) if m else ""
    except Exception:
        return ""


def _download_repo(target_repo: dict, dest: Path):
    """Download and extract the target repo tarball. Returns the repo root dir."""
    from django.conf import settings

    owner = target_repo["owner"]
    repo = target_repo["repo"]
    branch = target_repo.get("branch", "main")

    url = f"{GITHUB_API}/repos/{owner}/{repo}/tarball/{branch}"
    resp = requests.get(url, headers=_headers(settings.GITHUB_PAT), timeout=60)
    if resp.status_code != 200:
        logger.warning("test_run_tarball_failed", status=resp.status_code,
                       repo=f"{owner}/{repo}")
        return None

    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")

    # GitHub tarballs contain a single top-level directory
    subdirs = [p for p in dest.iterdir() if p.is_dir()]
    return subdirs[0] if subdirs else None
