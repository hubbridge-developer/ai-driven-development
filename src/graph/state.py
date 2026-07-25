"""AIDD Workflow State — shared TypedDict for all agents."""

from typing import TypedDict, Optional


class RelatedSpec(TypedDict):
    spec_id: str
    score: float
    match_type: str
    content: str


class ValidationResult(TypedDict):
    check: str
    is_valid: bool
    message: str


class AffectedFile(TypedDict):
    path: str
    action: str  # "create" | "modify"
    reason: str


class GeneratedFile(TypedDict):
    path: str
    action: str  # "create" | "modify"
    content: str
    language: str


class GeneratedTest(TypedDict):
    path: str
    content: str
    test_type: str  # "unit" | "integration"


class ImplementationTask(TypedDict):
    task_id: str
    description: str
    files: list[str]
    depends_on: list[str]


class CodePR(TypedDict):
    repo: str
    pr_number: int
    pr_url: str
    files: list[str]


class WorkflowState(TypedDict, total=False):
    # --- Input ---
    user_request: str
    workflow_id: str

    # --- Spec Discovery outputs ---
    related_specs: list[RelatedSpec]
    identified_namespaces: list[str]
    request_classification: str  # "new" | "update" | "bugfix"
    extends_spec: Optional[str]
    duplicate_warning: Optional[str]

    # --- Spec Generation outputs ---
    generated_spec: str
    spec_id: str
    low_confidence_sections: list[str]
    consistency_warnings: list[str]  # from consistency_checker sub-agent

    # --- Spec Validator outputs ---
    spec_validation_results: list[ValidationResult]
    spec_validation_retry_count: int
    spec_format_version: int

    # --- Approval Gate 1 ---
    spec_approval_status: str  # "pending" | "approved" | "rejected"
    spec_rejection_feedback: str
    spec_revision_count: int

    # --- Spec Publisher outputs ---
    spec_pr_url: Optional[str]
    spec_pr_number: Optional[int]
    spec_published: bool

    # --- Namespace Resolver outputs ---
    target_repositories: list[dict]
    affected_files: list[AffectedFile]
    code_context: str
    impact_summary: str

    # --- Code Developer outputs ---
    implementation_tasks: list[ImplementationTask]
    generated_files: list[GeneratedFile]
    generated_tests: list[GeneratedTest]
    integration_issues: list[dict]
    implementation_summary: str
    test_results: dict  # {status: passed|failed|error|skipped, exit_code?, summary}

    # --- Code Publisher outputs ---
    code_pr_url: Optional[str]
    code_pr_numbers: list[CodePR]
    code_published: bool

    # --- Approval Gate 2 ---
    code_approval_status: str  # "pending" | "approved" | "rejected"
    code_rejection_feedback: str
    code_revision_count: int

    # --- Code Review Handoff ---
    merge_results: list[dict]

    # --- Control ---
    current_agent: str
    error: Optional[str]
    final_status: str  # "completed" | "review-failed" | "error"
