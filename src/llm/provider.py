"""LLM abstraction layer — provider-agnostic interface via LiteLLM."""

import os
import json
import hashlib
import structlog
import yaml
from dataclasses import dataclass
from functools import lru_cache
from django.conf import settings
import litellm
from litellm import completion

# Configure Ollama API base if running in Docker
if os.getenv("OLLAMA_HOST"):
    litellm.api_base = os.getenv("OLLAMA_HOST")

# Configure Google Vertex AI if selected (GCP-native model service). Safe no-op
# when not configured — see src/llm/vertex_provider.py.
from src.llm.vertex_provider import configure_vertex, DEFAULT_VERTEX_MODEL

configure_vertex()

logger = structlog.get_logger()

# Default models per provider
PROVIDER_DEFAULTS = {
    "ollama": "ollama/mistral:7b",
    "litellm": "claude-sonnet-4-6",
    "claude": "claude-sonnet-4-6",
    "vertex": DEFAULT_VERTEX_MODEL,
}

# Per-agent model routing (can be overridden via config)
AGENT_MODEL_OVERRIDES = {
    "spec_generation": None,
    "spec_discovery": None,
    "spec_validator": None,  # Not used — deterministic
    "spec_publisher": None,
}


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def get_model_for_agent(agent_name: str) -> str:
    """Resolve the model to use for a given agent."""
    # 1) Env-configured routing file
    cfg = _routing_config().get(agent_name, {})
    if cfg.get("model"):
        return cfg["model"]

    # 2) Hard-coded overrides (kept for backward compatibility)
    override = AGENT_MODEL_OVERRIDES.get(agent_name)
    if override:
        return override

    # 3) Provider default fallback
    return PROVIDER_DEFAULTS.get(settings.LLM_PROVIDER, "ollama/codellama:7b")


def call_llm(
    prompt: str,
    system_prompt: str = "",
    agent_name: str = "default",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> LLMResponse:
    """Call LLM via LiteLLM with provider abstraction."""
    model = get_model_for_agent(agent_name)

    # Allow per-agent routing config to override generation params when provided
    cfg = _routing_config().get(agent_name, {})
    effective_max_tokens = cfg.get("max_tokens", max_tokens)
    effective_temperature = cfg.get("temperature", temperature)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    logger.info(
        "llm_call_start",
        agent=agent_name,
        model=model,
        prompt_length=len(prompt),
    )

    try:
        response = completion(
            model=model,
            messages=messages,
            max_tokens=effective_max_tokens,
            temperature=effective_temperature,
        )

        usage = response.usage
        result = LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
            total_tokens=usage.total_tokens or 0,
        )

        logger.info(
            "llm_call_complete",
            agent=agent_name,
            model=model,
            tokens=result.total_tokens,
        )
        return result

    except Exception as e:
        logger.error("llm_call_error", agent=agent_name, model=model, error=str(e))
        raise


@lru_cache(maxsize=1)
def _routing_config() -> dict:
    """Load per-agent routing config from YAML file if provided."""
    path = settings.LLM_ROUTING_CONFIG
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                logger.warning("llm_routing_config_invalid_type", path=path)
                return {}
            # Normalize keys to strings
            return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    except FileNotFoundError:
        logger.warning("llm_routing_config_missing", path=path)
    except Exception as e:
        logger.warning("llm_routing_config_error", path=path, error=str(e))
    return {}
