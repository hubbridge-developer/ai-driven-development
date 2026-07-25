"""Code Developer — orchestrates 5 sub-agents to implement code from spec."""

import structlog
from src.graph.state import WorkflowState

logger = structlog.get_logger()


def code_developer_agent(state: WorkflowState) -> dict:
    """Stage 6: Orchestrate code implementation via 5 sub-agents."""
    from src.graph.workflow import notify_sub_step  # late import to avoid circular dependency
    workflow_id = state.get("workflow_id", "")
    spec_id = state.get("spec_id", "")
    generated_spec = state.get("generated_spec", "")
    code_context = state.get("code_context", "")
    affected_files = state.get("affected_files", [])
    target_repos = state.get("target_repositories", [])

    if not target_repos:
        return {
            "current_agent": "code_developer",
            "error": "No target repositories available for code generation.",
        }

    target_repo = target_repos[0]  # POC: single repo
    stack_config = target_repo.get("stack_config", {})

    logger.info("code_developer_start", workflow_id=workflow_id, spec_id=spec_id)

    # Revision loop: inject reviewer feedback from the code approval gate
    rejection_feedback = ""
    if state.get("code_approval_status") == "rejected":
        rejection_feedback = state.get("code_rejection_feedback", "")
    if rejection_feedback:
        notify_sub_step(workflow_id, "code_developer", "Revision Feedback", spec_id=spec_id,
                        detail=f"Regenerating with reviewer feedback: {rejection_feedback[:80]}")
        code_context = (
            f"{code_context}\n\n"
            f"REVIEWER FEEDBACK ON PREVIOUS IMPLEMENTATION (must be addressed):\n"
            f"{rejection_feedback}"
        )

    # --- Sub-step 1: Task Planning ---
    notify_sub_step(workflow_id, "code_developer", "Task Planning", spec_id=spec_id,
                    detail=f"Sending spec + {len(affected_files)} affected files to LLM for task decomposition...")

    from src.agents.sub_agents.task_planner import plan_tasks
    implementation_tasks = plan_tasks(generated_spec, affected_files, stack_config,
                                      rejection_feedback=rejection_feedback)

    if not implementation_tasks:
        notify_sub_step(workflow_id, "code_developer", "Task Planning", spec_id=spec_id,
                        detail="LLM returned no tasks — aborting code generation")
        return {
            "current_agent": "code_developer",
            "implementation_tasks": [],
            "generated_files": [],
            "generated_tests": [],
            "integration_issues": [],
            "implementation_summary": "Task planning produced no tasks.",
        }

    # --- Sub-step 2: Code Writing ---
    task_summary = ", ".join(t.get("task_id", "?") for t in implementation_tasks)
    notify_sub_step(workflow_id, "code_developer", "Task Planning", spec_id=spec_id,
                    detail=f"Planned {len(implementation_tasks)} task(s): {task_summary}")
    for t in implementation_tasks:
        deps = t.get("depends_on", [])
        notify_sub_step(workflow_id, "code_developer", "Task Planning", spec_id=spec_id,
                        detail=f"  {t.get('task_id','?')}: {t.get('description','')[:70]}" + (f" (depends: {','.join(deps)})" if deps else ""))

    from src.agents.sub_agents.code_writer import write_code

    # Sort tasks by dependency order
    sorted_tasks = _topological_sort(implementation_tasks)
    notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                    detail=f"Dependency-sorted {len(sorted_tasks)} task(s) — starting code generation...")

    def _write_all_tasks(writer_context: str, label: str) -> list:
        """Run the code writer over all tasks, merging by path (later wins)."""
        files_acc = []
        for i, t in enumerate(sorted_tasks):
            notify_sub_step(workflow_id, "code_developer", label, spec_id=spec_id,
                            detail=f"  [{i+1}/{len(sorted_tasks)}] Generating {t.get('task_id', '')}...")
            new_files = write_code(t, generated_spec, writer_context, stack_config, target_repo)
            notify_sub_step(workflow_id, "code_developer", label, spec_id=spec_id,
                            detail=f"  Got {len(new_files)} file(s) for {t.get('task_id', '')}")
            for f in new_files:
                existing = next((g for g in files_acc if g["path"] == f["path"]), None)
                if existing:
                    files_acc.remove(existing)
                files_acc.append(f)
        return files_acc

    all_generated_files = []

    for idx, task in enumerate(sorted_tasks):
        task_desc = task.get("description", task.get("task_id", ""))
        task_files = task.get("files", [])
        notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                        detail=f"[{idx+1}/{len(sorted_tasks)}] {task.get('task_id','')}: {task_desc[:60]}")
        if task_files:
            notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                            detail=f"  Fetching existing files from GitHub: {', '.join(task_files[:3])}")
        notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                        detail=f"  Calling LLM to generate code for {task.get('task_id','')}...")
        files = write_code(task, generated_spec, code_context, stack_config, target_repo)
        notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                        detail=f"  LLM returned {len(files)} file(s): {', '.join(f['path'].split('/')[-1] for f in files[:3])}")
        # Merge: later tasks override earlier ones for same path
        for f in files:
            existing = next((g for g in all_generated_files if g["path"] == f["path"]), None)
            if existing:
                all_generated_files.remove(existing)
            all_generated_files.append(f)

    notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                    detail=f"Code generation complete — {len(all_generated_files)} total file(s)")

    if not all_generated_files:
        notify_sub_step(workflow_id, "code_developer", "Code Writing", spec_id=spec_id,
                        detail="LLM produced no parseable files — aborting code generation")
        return {
            "current_agent": "code_developer",
            "implementation_tasks": implementation_tasks,
            "generated_files": [],
            "generated_tests": [],
            "integration_issues": [],
            "implementation_summary": (
                "Code generation produced no files — the LLM output could not be "
                "parsed as JSON. Consider a stronger code model (see config/llm_routing_ollama.yaml)."
            ),
            "test_results": {"status": "skipped", "summary": "No code files were generated."},
        }

    # --- Sub-step 3: Test Writing ---
    test_fw = stack_config.get('test_framework', 'pytest')
    notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                    detail=f"Extracting acceptance criteria from spec for {test_fw} test generation...")

    from src.agents.sub_agents.test_writer import write_tests
    notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                    detail=f"Calling LLM to generate {test_fw} tests covering {len(all_generated_files)} code file(s)...")
    generated_tests = write_tests(generated_spec, all_generated_files, stack_config)

    if not generated_tests:
        notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                        detail="Test writer returned no tests — retrying once...")
        generated_tests = write_tests(generated_spec, all_generated_files, stack_config)
    tests_missing = not generated_tests
    if tests_missing:
        notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                        detail="⚠ No tests generated after retry — code will reach the "
                               "approval gate UNVERIFIED")

    for t in generated_tests[:3]:
        notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                        detail=f"  {t['path']} ({t.get('test_type', 'unit')})")
    notify_sub_step(workflow_id, "code_developer", "Test Writing", spec_id=spec_id,
                    detail=f"Generated {len(generated_tests)} test file(s)")

    # --- Sub-step 4: Integration Check ---
    from src.agents.sub_agents.integration_checker import check_integration
    from src.agents.sub_agents.code_verifier import check_syntax, check_preservation

    all_output_files = all_generated_files + [
        {"path": t["path"], "content": t["content"]} for t in generated_tests
    ]
    syntax_issues = check_syntax(all_output_files)
    notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                    detail=f"Syntax check (deterministic): {len(syntax_issues)} error(s) in {len(all_output_files)} file(s)")

    preservation_issues = check_preservation(all_generated_files, target_repo)
    notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                    detail=f"Preservation check (deterministic): {len(preservation_issues)} "
                           f"destructive modification(s) detected")

    notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                    detail=f"Sending {len(all_generated_files)} code + {len(generated_tests)} test files to LLM reviewer...")
    notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                    detail="Checking: imports, function signatures, model fields, circular deps...")

    integration_issues = syntax_issues + preservation_issues + check_integration(all_generated_files, generated_tests)

    # If critical issues found, retry code writer once
    critical_issues = [i for i in integration_issues if i.get("severity") == "critical"]
    warnings = [i for i in integration_issues if i.get("severity") == "warning"]

    for issue in integration_issues[:5]:
        sev = issue.get("severity", "?").upper()
        notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                        detail=f"  [{sev}] {issue.get('file', '?')}: {issue.get('description', '')[:70]}")
    notify_sub_step(workflow_id, "code_developer", "Integration Check", spec_id=spec_id,
                    detail=f"Review complete: {len(critical_issues)} critical, {len(warnings)} warning(s)")

    if critical_issues:
        logger.info("code_developer_retry", critical_issues=len(critical_issues))
        notify_sub_step(workflow_id, "code_developer", "Retry Code Writing", spec_id=spec_id,
                        detail=f"Critical issues found — re-generating code with fix instructions...")
        notify_sub_step(workflow_id, "code_developer", "Retry Code Writing", spec_id=spec_id,
                        detail=f"Injecting {len(critical_issues)} issue(s) as additional context for LLM")

        # Re-run code writer with integration feedback
        issues_context = "\n".join(
            f"- [{i['severity']}] {i.get('file', '')}: {i['description']}"
            for i in critical_issues
        )
        augmented_context = f"{code_context}\n\nINTEGRATION ISSUES TO FIX:\n{issues_context}"

        regenerated = _write_all_tasks(augmented_context, "Retry Code Writing")
        if regenerated:
            all_generated_files = regenerated

        # Re-check syntax + preservation + integration
        notify_sub_step(workflow_id, "code_developer", "Retry Code Writing", spec_id=spec_id,
                        detail="Re-running syntax + preservation + integration checks on fixed code...")
        all_output_files = all_generated_files + [
            {"path": t["path"], "content": t["content"]} for t in generated_tests
        ]
        integration_issues = (check_syntax(all_output_files)
                              + check_preservation(all_generated_files, target_repo)
                              + check_integration(all_generated_files, generated_tests))
        new_critical = sum(1 for i in integration_issues if i.get("severity") == "critical")
        notify_sub_step(workflow_id, "code_developer", "Retry Code Writing", spec_id=spec_id,
                        detail=f"After retry: {new_critical} critical issue(s) remaining (was {len(critical_issues)})")

    # --- Sub-step 5: Lint & Format ---
    total_files = len(all_generated_files) + len(generated_tests)
    notify_sub_step(workflow_id, "code_developer", "Lint & Format", spec_id=spec_id,
                    detail=f"Cleaning up {total_files} file(s) — fixing indentation, imports, whitespace...")

    from src.agents.sub_agents.lint_formatter import lint_and_format
    final_files = lint_and_format(all_generated_files, generated_tests, stack_config)
    notify_sub_step(workflow_id, "code_developer", "Lint & Format", spec_id=spec_id,
                    detail=f"Lint complete — {len(final_files)} file(s) cleaned and formatted")

    # Separate back into code files and test files
    test_paths = {t["path"] for t in generated_tests}
    final_code_files = [f for f in final_files if f["path"] not in test_paths]
    final_test_files = [
        {"path": f["path"], "content": f["content"],
         "test_type": next((t["test_type"] for t in generated_tests if t["path"] == f["path"]), "unit")}
        for f in final_files if f["path"] in test_paths
    ]

    # --- Sub-step 6: Test Execution ---
    from django.conf import settings
    test_results = {"status": "skipped",
                    "summary": "Test execution disabled (RUN_GENERATED_TESTS=false)."}
    if tests_missing:
        # Loud, not silent: unverified code must be visible at the approval gate.
        test_results = {
            "status": "error",
            "summary": "Test writer produced no tests (twice) — the generated code is UNVERIFIED. "
                       "Review with extra care or reject to retry.",
        }
    elif settings.RUN_GENERATED_TESTS:
        notify_sub_step(workflow_id, "code_developer", "Test Execution", spec_id=spec_id,
                        detail=f"Overlaying {len(final_code_files) + len(final_test_files)} file(s) on "
                               f"{target_repo.get('repo_slug', '?')} and running pytest...")
        from src.agents.sub_agents.code_verifier import run_generated_tests
        test_results = run_generated_tests(
            final_code_files, final_test_files, target_repo, settings.TEST_RUN_TIMEOUT
        )
        notify_sub_step(workflow_id, "code_developer", "Test Execution", spec_id=spec_id,
                        detail=f"Result: {test_results['status']} — "
                               f"{test_results.get('summary', '').splitlines()[-1][:90] if test_results.get('summary') else ''}")

        # --- Sub-step 7: Test Repair loop ---
        # Only real test failures trigger repair; "error" means the test
        # environment (not the code) is the problem, so retrying won't help.
        # The failure output is parsed to decide WHAT to regenerate: if the
        # file:line references point into the test files, the tests themselves
        # are broken (missing imports etc.) and regenerating code won't help.
        import re as _re
        repair_attempt = 0
        while (test_results.get("status") == "failed"
               and repair_attempt < settings.MAX_CODE_REVISION_CYCLES):
            repair_attempt += 1
            summary_txt = test_results.get("summary", "")

            ref_names = {r.split("/")[-1] for r in _re.findall(r"([\w./\-]+\.py):\d+", summary_txt)}
            code_names = {f["path"].split("/")[-1] for f in final_code_files}
            test_names = {t["path"].split("/")[-1] for t in final_test_files}
            failure_in_tests = bool(ref_names & test_names) and not (ref_names & code_names)

            if failure_in_tests:
                notify_sub_step(workflow_id, "code_developer", "Test Repair", spec_id=spec_id,
                                detail=f"Repair {repair_attempt}/{settings.MAX_CODE_REVISION_CYCLES}: failure is "
                                       f"inside the TEST file(s) — regenerating tests, not code...")
                new_tests = write_tests(generated_spec, final_code_files, stack_config,
                                        failure_feedback=summary_txt)
                if not new_tests:
                    notify_sub_step(workflow_id, "code_developer", "Test Repair", spec_id=spec_id,
                                    detail="Test regeneration produced nothing — stopping repair loop")
                    break
                generated_tests = new_tests
                test_paths = {t["path"] for t in generated_tests}
                final_files = lint_and_format(final_code_files, generated_tests, stack_config)
            else:
                notify_sub_step(workflow_id, "code_developer", "Test Repair", spec_id=spec_id,
                                detail=f"Repair {repair_attempt}/{settings.MAX_CODE_REVISION_CYCLES}: "
                                       f"regenerating implementation against failure output...")
                repair_context = (
                    f"{code_context}\n\nFAILING TEST OUTPUT — fix the implementation so these "
                    f"tests pass (do NOT modify the tests):\n{summary_txt}"
                )
                regenerated = _write_all_tasks(repair_context, "Test Repair")
                if not regenerated:
                    notify_sub_step(workflow_id, "code_developer", "Test Repair", spec_id=spec_id,
                                    detail="Regeneration produced no files — stopping repair loop")
                    break
                final_files = lint_and_format(regenerated, final_test_files, stack_config)

            final_code_files = [f for f in final_files if f["path"] not in test_paths]
            final_test_files = [
                {"path": f["path"], "content": f["content"],
                 "test_type": next((t["test_type"] for t in generated_tests if t["path"] == f["path"]), "unit")}
                for f in final_files if f["path"] in test_paths
            ]

            test_results = run_generated_tests(
                final_code_files, final_test_files, target_repo, settings.TEST_RUN_TIMEOUT
            )
            notify_sub_step(workflow_id, "code_developer", "Test Repair", spec_id=spec_id,
                            detail=f"After repair {repair_attempt}: {test_results.get('status')}")

    # Build implementation summary
    implementation_summary = _build_summary(
        implementation_tasks, final_code_files, final_test_files, integration_issues,
        test_results,
    )

    logger.info(
        "code_developer_complete",
        workflow_id=workflow_id,
        tasks=len(implementation_tasks),
        files=len(final_code_files),
        tests=len(final_test_files),
        issues=len(integration_issues),
    )

    return {
        "current_agent": "code_developer",
        "implementation_tasks": implementation_tasks,
        "generated_files": final_code_files,
        "generated_tests": final_test_files,
        "integration_issues": integration_issues,
        "implementation_summary": implementation_summary,
        "test_results": test_results,
    }


def _topological_sort(tasks: list[dict]) -> list[dict]:
    """Sort tasks by dependency order (simple topological sort)."""
    task_map = {t["task_id"]: t for t in tasks}
    visited = set()
    result = []

    def visit(task_id):
        if task_id in visited:
            return
        visited.add(task_id)
        task = task_map.get(task_id)
        if task:
            for dep in task.get("depends_on", []):
                visit(dep)
            result.append(task)

    for t in tasks:
        visit(t["task_id"])

    return result


def _build_summary(tasks: list, files: list, tests: list, issues: list,
                   test_results: dict = None) -> str:
    """Build human-readable implementation summary."""
    lines = [
        f"## Implementation Summary",
        f"",
        f"**Tasks:** {len(tasks)} implementation tasks completed",
        f"**Files:** {len(files)} code files generated",
        f"**Tests:** {len(tests)} test files generated",
        f"",
    ]

    if tasks:
        lines.append("### Tasks")
        for t in tasks:
            lines.append(f"- {t.get('task_id', '?')}: {t.get('description', '')}")
        lines.append("")

    if files:
        lines.append("### Files Changed")
        for f in files:
            lines.append(f"- `{f['path']}` ({f.get('action', 'create')})")
        lines.append("")

    if tests:
        lines.append("### Tests")
        for t in tests:
            lines.append(f"- `{t['path']}` ({t.get('test_type', 'unit')})")
        lines.append("")

    if issues:
        critical = [i for i in issues if i.get("severity") == "critical"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        if critical:
            lines.append(f"### ⚠ Critical Issues ({len(critical)})")
            for i in critical:
                lines.append(f"- {i.get('file', '')}: {i.get('description', '')}")
            lines.append("")
        if warnings:
            lines.append(f"### Warnings ({len(warnings)})")
            for i in warnings:
                lines.append(f"- {i.get('file', '')}: {i.get('description', '')}")
            lines.append("")

    if test_results and test_results.get("status") != "skipped":
        status = test_results.get("status", "?")
        icon = {"passed": "✅", "failed": "❌"}.get(status, "⚠")
        lines.append(f"### Test Run: {icon} {status}")
        summary = test_results.get("summary", "")
        if summary:
            lines.append("```")
            lines.append(summary)
            lines.append("```")

    return "\n".join(lines)
