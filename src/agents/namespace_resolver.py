"""Namespace Resolver — maps approved spec to target code repositories and builds code context."""

import structlog
from src.graph.state import WorkflowState

logger = structlog.get_logger()


def namespace_resolver_agent(state: WorkflowState) -> dict:
    """Stage 5: Resolve target repos and build code context for code generation."""
    from src.graph.workflow import notify_sub_step  # late import to avoid circular dependency
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")
    namespaces = state.get("identified_namespaces", [])

    logger.info("namespace_resolver_start", workflow_id=workflow_id, spec_id=spec_id)

    # --- Sub-step 1: Load Repositories ---
    notify_sub_step(workflow_id, "namespace_resolver", "Load Repositories", spec_id=spec_id,
                    detail=f"Querying DB for repos linked to {len(namespaces)} namespace(s): {', '.join(namespaces)}")

    from src.aidd_api.models import Namespace, Repository
    from django.conf import settings

    target_repositories = []
    for ns_name in namespaces:
        try:
            ns = Namespace.objects.get(name=ns_name)
            repos = Repository.objects.filter(namespace=ns)
            notify_sub_step(workflow_id, "namespace_resolver", "Load Repositories", spec_id=spec_id,
                            detail=f"Namespace '{ns_name}': found {repos.count()} repo(s)")
            for repo in repos:
                owner, repo_name = repo.repo_slug.split("/", 1)
                # Token is intentionally NOT stored here — target_repositories is
                # persisted in state_snapshot and exposed via the REST API.
                target_repositories.append({
                    "owner": owner,
                    "repo": repo_name,
                    "repo_slug": repo.repo_slug,
                    "branch": "main",
                    "stack_config": ns.stack_config,
                    "namespace": ns_name,
                })
                notify_sub_step(workflow_id, "namespace_resolver", "Load Repositories", spec_id=spec_id,
                                detail=f"Added target: {repo.repo_slug} (stack: {ns.stack_config.get('language', '?')}/{ns.stack_config.get('framework', '?')})")
        except Namespace.DoesNotExist:
            notify_sub_step(workflow_id, "namespace_resolver", "Load Repositories", spec_id=spec_id,
                            detail=f"Namespace '{ns_name}' not found in DB — skipping")
            logger.warning("namespace_not_found", namespace=ns_name)

    if not target_repositories:
        logger.warning("no_target_repositories", namespaces=namespaces)
        return {
            "current_agent": "namespace_resolver",
            "target_repositories": [],
            "affected_files": [],
            "code_context": "",
            "impact_summary": "No target repositories found for the identified namespaces.",
        }

    # --- Sub-step 2: Scan Repository ---
    repo_info = target_repositories[0]  # POC: single repo
    notify_sub_step(workflow_id, "namespace_resolver", "Scan Repository", spec_id=spec_id,
                    detail=f"Calling GitHub API: GET /repos/{repo_info['repo_slug']}/git/trees (recursive)...")

    from src.agents.sub_agents.repo_scanner import scan_repository

    file_tree, dependency_map = scan_repository(
        repo_info["owner"], repo_info["repo"], repo_info["branch"], settings.GITHUB_PAT
    )

    notify_sub_step(workflow_id, "namespace_resolver", "Scan Repository", spec_id=spec_id,
                    detail=f"Scanned: {len(file_tree)} source files, {len(dependency_map)} dependencies")
    if dependency_map:
        top_deps = list(dependency_map.keys())[:5]
        notify_sub_step(workflow_id, "namespace_resolver", "Scan Repository", spec_id=spec_id,
                        detail=f"Key dependencies: {', '.join(top_deps)}" + (f" +{len(dependency_map)-5} more" if len(dependency_map) > 5 else ""))

    # --- Sub-step 3: Analyze Impact ---
    notify_sub_step(workflow_id, "namespace_resolver", "Analyze Impact", spec_id=spec_id,
                    detail=f"Sending spec + {len(file_tree)} files to LLM for impact analysis...")

    from src.agents.sub_agents.impact_analyzer import analyze_impact

    generated_spec = state.get("generated_spec", "")
    affected_files, impact_summary = analyze_impact(
        generated_spec, file_tree, dependency_map, repo_info["stack_config"]
    )

    notify_sub_step(workflow_id, "namespace_resolver", "Analyze Impact", spec_id=spec_id,
                    detail=f"LLM identified {len(affected_files)} affected file(s)")
    for af in affected_files[:4]:
        notify_sub_step(workflow_id, "namespace_resolver", "Analyze Impact", spec_id=spec_id,
                        detail=f"  [{af['action']}] {af['path']} — {af.get('reason', '')[:60]}")
    if len(affected_files) > 4:
        notify_sub_step(workflow_id, "namespace_resolver", "Analyze Impact", spec_id=spec_id,
                        detail=f"  ... +{len(affected_files)-4} more file(s)")

    # --- Sub-step 4: Build Code Context ---
    notify_sub_step(workflow_id, "namespace_resolver", "Build Code Context", spec_id=spec_id,
                    detail=f"Assembling context for Code Developer ({len(file_tree)} files, {len(affected_files)} affected)...")

    code_context = _build_code_context(
        repo_info, file_tree, affected_files, dependency_map, settings.CODE_CONTEXT_MAX_CHARS
    )
    notify_sub_step(workflow_id, "namespace_resolver", "Build Code Context", spec_id=spec_id,
                    detail=f"Context built: {len(code_context)} chars (max {settings.CODE_CONTEXT_MAX_CHARS})")

    logger.info(
        "namespace_resolver_complete",
        workflow_id=workflow_id,
        repos=len(target_repositories),
        affected_files=len(affected_files),
    )

    return {
        "current_agent": "namespace_resolver",
        "target_repositories": target_repositories,
        "affected_files": affected_files,
        "code_context": code_context,
        "impact_summary": impact_summary,
    }


def _build_code_context(repo_info: dict, file_tree: list, affected_files: list,
                        dependency_map: dict, max_chars: int) -> str:
    """Build a formatted context string for the Code Developer."""
    lines = [
        f"Repository: {repo_info['repo_slug']}",
        f"Stack: {repo_info['stack_config']}",
        "",
        "File Tree (source files):",
    ]
    for f in file_tree[:50]:  # Limit tree display
        lines.append(f"  {f}")

    lines.append("")
    lines.append("Affected Files:")
    for af in affected_files:
        lines.append(f"  [{af.get('action', '?')}] {af.get('path', '?')} — {af.get('reason', '')}")

    if dependency_map:
        lines.append("")
        lines.append("Dependencies:")
        for dep, version in list(dependency_map.items())[:20]:
            lines.append(f"  {dep}: {version}")

    context = "\n".join(lines)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n... (truncated)"
    return context
