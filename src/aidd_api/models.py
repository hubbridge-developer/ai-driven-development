import uuid
from django.db import models


class Namespace(models.Model):
    """Logical business domain (auth, payments, notifications, etc.)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    owners = models.JSONField(default=list, blank=True)
    stack_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="language, framework, test_framework, build_tool",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Track next spec sequence per namespace
    next_spec_sequence = models.IntegerField(default=1)

    def allocate_spec_id(self) -> str:
        spec_id = f"SPEC-{self.name.upper()}-{self.next_spec_sequence:04d}"
        self.next_spec_sequence += 1
        self.save(update_fields=["next_spec_sequence"])
        return spec_id

    def __str__(self):
        return self.name


class SpecRepoConfig(models.Model):
    """Configuration for the spec repository (where specs are published)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spec_repo_url = models.URLField(help_text="GitHub repo URL for specs")
    branch = models.CharField(max_length=200, default="main")
    encrypted_token = models.BinaryField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.spec_repo_url} ({'active' if self.active else 'inactive'})"


class Repository(models.Model):
    """Target code repository linked to a namespace."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    namespace = models.ForeignKey(
        Namespace, on_delete=models.CASCADE, related_name="repositories"
    )
    repo_slug = models.CharField(max_length=200, help_text="e.g. org/backend")
    paths = models.JSONField(default=list, blank=True)
    encrypted_token = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["namespace", "repo_slug"]

    def __str__(self):
        return f"{self.repo_slug} ({self.namespace.name})"


class WorkflowRun(models.Model):
    """Tracks a single spec-driven workflow execution."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        WAITING_APPROVAL = "waiting_approval", "Waiting for Approval"
        WAITING_CODE_APPROVAL = "waiting_code_approval", "Waiting for Code Approval"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.RUNNING
    )
    current_agent = models.CharField(max_length=100, blank=True, default="")
    user_request = models.TextField()
    state_snapshot = models.JSONField(default=dict, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.workflow_id} [{self.status}]"


class GeneratedSpec(models.Model):
    """Stores generated specifications linked to a workflow run."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_run = models.ForeignKey(
        WorkflowRun, on_delete=models.CASCADE, related_name="specs"
    )
    spec_id = models.CharField(max_length=50, db_index=True)
    namespace = models.CharField(max_length=100)
    content = models.TextField()
    version = models.IntegerField(default=1)
    indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["spec_id", "version"]

    def __str__(self):
        return f"{self.spec_id} v{self.version}"


class GeneratedCode(models.Model):
    """Track generated code output per workflow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_run = models.ForeignKey(
        WorkflowRun, on_delete=models.CASCADE, related_name="codes"
    )
    spec = models.ForeignKey(
        GeneratedSpec, on_delete=models.CASCADE, related_name="codes",
        null=True, blank=True,
    )
    files = models.JSONField(default=list)  # [{path, action, content, language}]
    tests = models.JSONField(default=list)  # [{path, content, test_type}]
    implementation_summary = models.TextField(blank=True, default="")
    code_pr_url = models.URLField(null=True, blank=True)
    code_pr_numbers = models.JSONField(default=list)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        spec_id = self.spec.spec_id if self.spec else "unknown"
        return f"Code for {spec_id} v{self.version}"
