from rest_framework import serializers
from src.aidd_api.models import Namespace, WorkflowRun, GeneratedSpec, SpecRepoConfig


class NamespaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Namespace
        fields = [
            "id", "name", "description", "owners", "stack_config",
            "next_spec_sequence", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "next_spec_sequence", "created_at", "updated_at"]


class GeneratedSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedSpec
        fields = ["id", "spec_id", "namespace", "content", "version", "indexed_at", "created_at"]


def sanitize_state_snapshot(state: dict) -> dict:
    """Strip repo tokens from a state snapshot before exposing it via the API.

    Newer runs never store tokens in state, but snapshots persisted by older
    runs may still contain them in target_repositories.
    """
    if not state:
        return state
    repos = state.get("target_repositories")
    if isinstance(repos, list):
        state = {
            **state,
            "target_repositories": [
                {k: v for k, v in r.items() if k != "token"} if isinstance(r, dict) else r
                for r in repos
            ],
        }
    return state


class WorkflowRunSerializer(serializers.ModelSerializer):
    specs = GeneratedSpecSerializer(many=True, read_only=True)
    state_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowRun
        fields = [
            "id", "workflow_id", "status", "current_agent", "user_request",
            "state_snapshot", "token_usage", "error", "created_at", "updated_at",
            "specs",
        ]

    def get_state_snapshot(self, obj):
        return sanitize_state_snapshot(obj.state_snapshot)


class WorkflowStartSerializer(serializers.Serializer):
    user_request = serializers.CharField(min_length=5, max_length=5000)


class WorkflowApproveSerializer(serializers.Serializer):
    pass  # No body needed


class WorkflowRejectSerializer(serializers.Serializer):
    feedback = serializers.CharField(min_length=1, max_length=5000)


class SpecRepoConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecRepoConfig
        fields = ["id", "spec_repo_url", "branch", "active", "created_at"]
        read_only_fields = ["id", "created_at"]
