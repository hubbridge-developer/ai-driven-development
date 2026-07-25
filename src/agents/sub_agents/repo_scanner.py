"""Repository Scanner — fetches file tree and dependency map via GitHub API."""

import structlog
import requests
from src.github.service import _headers, GITHUB_API

logger = structlog.get_logger()

# Source file extensions by language
SOURCE_EXTENSIONS = {
    "python": {".py"},
    "javascript": {".js", ".jsx", ".ts", ".tsx"},
    "java": {".java"},
    "go": {".go"},
    "ruby": {".rb"},
}

# Dependency files by language
DEPENDENCY_FILES = {
    "python": ["requirements.txt", "Pipfile", "pyproject.toml", "setup.py"],
    "javascript": ["package.json"],
    "java": ["pom.xml", "build.gradle"],
    "go": ["go.mod"],
}


def scan_repository(owner: str, repo: str, branch: str, token: str) -> tuple[list[str], dict]:
    """Scan a GitHub repository and return (file_tree, dependency_map).

    file_tree: list of source file paths
    dependency_map: dict of {package: version} from dependency files
    """
    logger.info("repo_scan_start", owner=owner, repo=repo, branch=branch)

    # Fetch recursive tree
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = requests.get(url, headers=_headers(token), timeout=30)

    if resp.status_code != 200:
        logger.error("repo_scan_tree_failed", status=resp.status_code, body=resp.text[:200])
        return [], {}

    tree_data = resp.json()
    all_files = [item["path"] for item in tree_data.get("tree", []) if item["type"] == "blob"]

    # Filter to source files (detect language from files if not obvious)
    language = _detect_language(all_files)
    extensions = SOURCE_EXTENSIONS.get(language, {".py"})
    source_files = [f for f in all_files if any(f.endswith(ext) for ext in extensions)]

    # Parse dependency files
    dependency_map = {}
    dep_files = DEPENDENCY_FILES.get(language, [])
    for dep_file in dep_files:
        if dep_file in all_files:
            deps = _fetch_and_parse_deps(owner, repo, branch, dep_file, token, language)
            dependency_map.update(deps)

    logger.info(
        "repo_scan_complete",
        total_files=len(all_files),
        source_files=len(source_files),
        dependencies=len(dependency_map),
        language=language,
    )

    return source_files, dependency_map


def _detect_language(files: list[str]) -> str:
    """Detect the primary language from file extensions."""
    counts = {}
    for f in files:
        for lang, exts in SOURCE_EXTENSIONS.items():
            if any(f.endswith(ext) for ext in exts):
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "python"
    return max(counts, key=counts.get)


def _fetch_and_parse_deps(owner: str, repo: str, branch: str, path: str,
                          token: str, language: str) -> dict:
    """Fetch a dependency file from GitHub and parse it."""
    import base64

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if resp.status_code != 200:
        return {}

    content = base64.b64decode(resp.json()["content"]).decode("utf-8")

    if language == "python" and path == "requirements.txt":
        return _parse_requirements_txt(content)
    elif language == "javascript" and path == "package.json":
        return _parse_package_json(content)
    return {}


def _parse_requirements_txt(content: str) -> dict:
    """Parse requirements.txt into {package: version}."""
    deps = {}
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            deps[name.strip()] = version.strip()
        elif ">=" in line:
            name, version = line.split(">=", 1)
            deps[name.strip()] = f">={version.strip()}"
        else:
            deps[line] = "*"
    return deps


def _parse_package_json(content: str) -> dict:
    """Parse package.json dependencies."""
    import json
    try:
        data = json.loads(content)
        deps = {}
        deps.update(data.get("dependencies", {}))
        deps.update(data.get("devDependencies", {}))
        return deps
    except Exception:
        return {}
