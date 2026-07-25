"""Google Vertex AI provider wiring (GCP-native, the future default on GKE).

This is the GCP analogue of "AWS Bedrock": a managed, first-party model service.
Because the whole platform already routes every model call through LiteLLM
(`src.llm.provider.call_llm`), enabling Vertex is just configuration — LiteLLM
speaks the `vertex_ai/<model>` protocol natively. No agent code changes.

To turn it on:
    LLM_PROVIDER=vertex
    VERTEX_PROJECT=my-gcp-project
    VERTEX_LOCATION=us-central1
    # Auth: on GKE use Workload Identity (no key file needed). Off-cluster set
    # GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

Per-agent model routing still works via the routing YAML, e.g.
    code_developer: { model: "vertex_ai/gemini-1.5-pro" }

This module is a thin, side-effect-light stub: it configures LiteLLM's Vertex
defaults when the env is present. It is intentionally safe to import even when
Vertex is not configured.
"""

import os
import structlog

logger = structlog.get_logger()

# Default Vertex model when the provider is selected but no per-agent override
# is set. Override without code changes via the VERTEX_MODEL env var (ConfigMap).
DEFAULT_VERTEX_MODEL = os.getenv("VERTEX_MODEL", "vertex_ai/gemini-2.0-flash-001")


def configure_vertex() -> bool:
    """Wire LiteLLM to Vertex AI from environment variables.

    Returns True if Vertex settings were applied, False if not configured.
    Safe to call unconditionally at import time.
    """
    project = os.getenv("VERTEX_PROJECT") or os.getenv("VERTEXAI_PROJECT")
    location = os.getenv("VERTEX_LOCATION") or os.getenv("VERTEXAI_LOCATION") or "us-central1"

    if not project:
        return False

    try:
        import litellm

        litellm.vertex_project = project
        litellm.vertex_location = location
        logger.info("vertex_configured", project=project, location=location)
        return True
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("vertex_configure_failed", error=str(e))
        return False
