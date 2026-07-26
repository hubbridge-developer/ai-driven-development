"""LLM abstraction layer — provider-agnostic interface via LiteLLM."""

import os
import json
import hashlib
import threading
import structlog
import yaml
from dataclasses import dataclass
from functools import lru_cache
from django.conf import settings
import litellm
from litellm import completion

# Ollama's API base. IMPORTANT: pass this per-call for ollama/* models only —
# setting litellm.api_base globally hijacks every other provider that honors it
# (e.g. OpenRouter would get redirected to the Ollama container and 404). See
# call_llm below, where it's applied only when the model is an ollama model.
OLLAMA_API_BASE = os.getenv("OLLAMA_HOST")

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
    # Google AI Studio free tier (LiteLLM reads GEMINI_API_KEY from env).
    "gemini": "gemini/gemini-2.5-flash",
    # Groq free tier (LiteLLM reads GROQ_API_KEY from env).
    "groq": "groq/llama-3.3-70b-versatile",
    # OpenRouter free tier (LiteLLM reads OPENROUTER_API_KEY from env).
    "openrouter": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
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
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Per-stage usage accumulator. The pipeline runs one stage at a time in a single
# background thread, so a thread-local running total is exactly "this stage's
# LLM usage" once reset at the start of the stage (see graph/workflow.py).
# ---------------------------------------------------------------------------
_usage = threading.local()


def _acc() -> dict:
    if not hasattr(_usage, "data"):
        reset_usage()
    return _usage.data


def reset_usage() -> None:
    _usage.data = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                   "total_tokens": 0, "cost_usd": 0.0}


def get_usage() -> dict:
    return dict(_acc())


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

    # Apply the Ollama base URL ONLY for ollama/* models. Other providers
    # (groq, openrouter, vertex, ...) must use their own default endpoints.
    extra: dict = {}
    if model.startswith("ollama/") and OLLAMA_API_BASE:
        extra["api_base"] = OLLAMA_API_BASE

    try:
        response = completion(
            model=model,
            messages=messages,
            max_tokens=effective_max_tokens,
            temperature=effective_temperature,
            **extra,
        )

        usage = response.usage

        # Cost (USD) — LiteLLM knows pricing for Vertex/Gemini, Claude, etc.
        # Local models (Ollama) are free, so this is ~0.0 there.
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:
            cost = 0.0

        result = LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
            total_tokens=usage.total_tokens or 0,
            cost_usd=cost,
        )

        # accumulate into the current stage's running total
        d = _acc()
        d["calls"] += 1
        d["prompt_tokens"] += result.prompt_tokens
        d["completion_tokens"] += result.completion_tokens
        d["total_tokens"] += result.total_tokens
        d["cost_usd"] += cost

        logger.info(
            "llm_call_complete",
            agent=agent_name,
            model=model,
            tokens=result.total_tokens,
            cost_usd=round(cost, 6),
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
