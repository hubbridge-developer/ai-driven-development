"""GitHub REST API service — create branches, commit files, open PRs."""

import re
import base64
import structlog
import requests
from django.conf import settings

logger = structlog.get_logger()

GITHUB_API = "https://api.github.com"


def _parse_repo_owner_name(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL.

    Supports:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
    """
    match = re.match(r"https?://github\.com/([^/]+)/([^/.]+)", repo_url)
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url}")
    return match.group(1), match.group(2)


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_default_branch_sha(owner: str, repo: str, branch: str, token: str) -> str:
    """Get the latest commit SHA of the base branch.

    If the repo is empty (no commits), initializes it with a README first.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    resp = requests.get(url, headers=_headers(token), timeout=30)

    if resp.status_code in (404, 409):
        # Repo is empty — initialize with a README to create the default branch
        logger.info("github_repo_empty", owner=owner, repo=repo, branch=branch)
        init_url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/README.md"
        init_resp = requests.put(
            init_url,
            json={
                "message": "Initialize spec repository",
                "content": base64.b64encode(
                    f"# {repo}\n\nAIDD specification repository.\n".encode()
                ).decode("ascii"),
            },
            headers=_headers(token),
            timeout=30,
        )
        init_resp.raise_for_status()
        logger.info("github_repo_initialized", owner=owner, repo=repo)

        # Retry getting the branch SHA
        resp = requests.get(url, headers=_headers(token), timeout=30)

    resp.raise_for_status()
    return resp.json()["object"]["sha"]


def create_branch(owner: str, repo: str, branch_name: str, base_sha: str, token: str):
    """Create a new branch from the given SHA."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
    resp = requests.post(url, json=payload, headers=_headers(token), timeout=30)
    if resp.status_code == 422 and "Reference already exists" in resp.text:
        logger.info("github_branch_exists", branch=branch_name)
        return
    resp.raise_for_status()
    logger.info("github_branch_created", branch=branch_name)


def commit_file(
    owner: str,
    repo: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str,
    token: str,
) -> str:
    """Create or update a file on the given branch. Returns the commit SHA."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"

    # Check if file already exists (to get its SHA for update)
    existing_sha = None
    resp = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=30)
    if resp.status_code == 200:
        existing_sha = resp.json().get("sha")

    payload = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    resp = requests.put(url, json=payload, headers=_headers(token), timeout=30)
    resp.raise_for_status()

    commit_sha = resp.json()["commit"]["sha"]
    logger.info("github_file_committed", path=file_path, branch=branch, sha=commit_sha[:8])
    return commit_sha


def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str,
    token: str,
    draft: bool = False,
) -> dict:
    """Open a pull request. Returns {"url": ..., "number": ...}."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch,
        "draft": draft,
    }
    resp = requests.post(url, json=payload, headers=_headers(token), timeout=30)

    # If PR already exists for this branch, find it
    if resp.status_code == 422 and "A pull request already exists" in resp.text:
        existing = requests.get(
            url,
            params={"head": f"{owner}:{head_branch}", "state": "open"},
            headers=_headers(token),
            timeout=30,
        )
        if existing.status_code == 200 and existing.json():
            pr = existing.json()[0]
            logger.info("github_pr_exists", number=pr["number"])
            return {"url": pr["html_url"], "number": pr["number"]}

    resp.raise_for_status()
    pr_data = resp.json()
    logger.info("github_pr_created", number=pr_data["number"], url=pr_data["html_url"])
    return {"url": pr_data["html_url"], "number": pr_data["number"]}


def mark_pull_request_ready(owner: str, repo: str, pr_number: int, token: str) -> bool:
    """Flip a draft PR to ready-for-review.

    GitHub has no REST endpoint for this — it requires the GraphQL
    markPullRequestReadyForReview mutation.
    """
    pr = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_headers(token), timeout=30,
    )
    pr.raise_for_status()
    data = pr.json()
    if not data.get("draft"):
        return True

    resp = requests.post(
        "https://api.github.com/graphql",
        json={
            "query": "mutation($id: ID!) { markPullRequestReadyForReview(input: {pullRequestId: $id}) { pullRequest { isDraft } } }",
            "variables": {"id": data["node_id"]},
        },
        headers=_headers(token), timeout=30,
    )
    resp.raise_for_status()
    out = resp.json()
    if out.get("errors"):
        logger.error("github_mark_ready_failed", pr=pr_number, errors=out["errors"])
        return False
    logger.info("github_pr_marked_ready", pr=pr_number)
    return True


def publish_spec_to_github(
    spec_id: str,
    namespace: str,
    spec_content: str,
    user_request: str,
    repo_url: str = "",
    base_branch: str = "main",
    token: str = "",
) -> dict:
    """Full publish flow: create branch → commit spec file → open PR.

    Returns:
        {"spec_pr_url": "...", "spec_pr_number": N}
    """
    # Resolve config
    repo_url = repo_url or settings.SPEC_REPO_URL
    token = token or settings.GITHUB_PAT
    if not repo_url or not token:
        raise ValueError("SPEC_REPO_URL and GITHUB_PAT must be configured")

    owner, repo = _parse_repo_owner_name(repo_url)

    # Branch name: spec/SPEC-PAYMENTS-0003
    branch_name = f"spec/{spec_id.lower()}"

    # File path: specs/{namespace}/{SPEC_ID}.md
    ns_folder = namespace or "general"
    file_path = f"specs/{ns_folder}/{spec_id}.md"

    # Render spec as markdown
    rendered_md = _render_spec_markdown(spec_id, namespace, spec_content, user_request)

    # Commit message
    commit_message = f"Add specification {spec_id}\n\nUser request: {user_request[:200]}"

    logger.info(
        "github_publish_start",
        spec_id=spec_id,
        owner=owner,
        repo=repo,
        branch=branch_name,
        file_path=file_path,
    )

    # Step 1: Get base branch SHA
    base_sha = get_default_branch_sha(owner, repo, base_branch, token)

    # Step 2: Create feature branch
    create_branch(owner, repo, branch_name, base_sha, token)

    # Step 3: Commit the spec file
    commit_file(owner, repo, branch_name, file_path, rendered_md, commit_message, token)

    # Step 4: Open pull request
    pr_title = f"[{spec_id}] {user_request[:80]}"
    pr_body = _render_pr_body(spec_id, namespace, user_request, spec_content)
    pr = create_pull_request(owner, repo, pr_title, pr_body, branch_name, base_branch, token)

    logger.info(
        "github_publish_complete",
        spec_id=spec_id,
        pr_url=pr["url"],
        pr_number=pr["number"],
    )

    return {"spec_pr_url": pr["url"], "spec_pr_number": pr["number"]}


def _render_spec_markdown(
    spec_id: str,
    namespace: str,
    spec_content: str,
    user_request: str,
) -> str:
    """Render the XML-tagged spec into a readable markdown document."""
    import re
    import yaml

    lines = [
        f"# {spec_id}",
        "",
    ]

    # Extract and render spec_header
    header_match = re.search(r"<spec_header>(.*?)</spec_header>", spec_content, re.DOTALL)
    if header_match:
        lines.append("## Spec Header")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        try:
            header = yaml.safe_load(header_match.group(1).strip())
            if isinstance(header, dict):
                for k, v in header.items():
                    lines.append(f"| {k} | {v} |")
        except Exception:
            lines.append(f"```yaml\n{header_match.group(1).strip()}\n```")
        lines.append("")

    # User request
    lines.append("## User Request")
    lines.append("")
    lines.append(f"> {user_request}")
    lines.append("")

    # Render each section
    section_order = ["summary", "background", "requirements", "technical_design", "acceptance_criteria", "dependencies"]
    section_titles = {
        "summary": "Summary",
        "background": "Background",
        "requirements": "Requirements",
        "technical_design": "Technical Design",
        "acceptance_criteria": "Acceptance Criteria",
        "dependencies": "Dependencies",
    }

    for section in section_order:
        pattern = rf"<{section}>(.*?)</{section}>"
        match = re.search(pattern, spec_content, re.DOTALL)
        if match:
            content = match.group(1).strip()
            title = section_titles.get(section, section.replace("_", " ").title())
            lines.append(f"## {title}")
            lines.append("")
            # For acceptance_criteria, render as-is (already markdown checkboxes)
            if section == "acceptance_criteria":
                lines.append(content)
            else:
                # Wrap YAML-like content in code block
                lines.append("```yaml")
                lines.append(content)
                lines.append("```")
            lines.append("")

    # Raw spec at the bottom
    lines.append("---")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Raw Spec (XML)</summary>")
    lines.append("")
    lines.append("```xml")
    lines.append(spec_content)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)


def _render_pr_body(
    spec_id: str,
    namespace: str,
    user_request: str,
    spec_content: str,
) -> str:
    """Render the pull request description body."""
    import re

    # Extract summary
    summary = ""
    match = re.search(r"<summary>(.*?)</summary>", spec_content, re.DOTALL)
    if match:
        summary = match.group(1).strip()

    return f"""## Specification: {spec_id}

**Namespace:** `{namespace}`
**User Request:** {user_request}

### Summary

{summary}

---

*This PR was automatically created by the AIDD spec-publisher agent.*
*Review the specification file and approve to merge into the spec repository.*
"""
