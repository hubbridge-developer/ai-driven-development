import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "src.add_api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "add_project.urls"
WSGI_APPLICATION = "add_project.wsgi.application"
ASGI_APPLICATION = "add_project.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://add:add@localhost:5432/add")
_db_parts = DATABASE_URL.replace("postgresql://", "").replace("postgres://", "")
_userpass, _hostdb = _db_parts.split("@")
_user, _password = _userpass.split(":")
_host_port, _dbname = _hostdb.split("/")
_host_parts = _host_port.split(":")
_host = _host_parts[0]
_port = _host_parts[1] if len(_host_parts) > 1 else "5432"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _dbname,
        "USER": _user,
        "PASSWORD": _password,
        "HOST": _host,
        "PORT": _port,
    }
}

# Redis / Channels
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# CSRF
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8001",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8001",
]

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    # Generates the OpenAPI schema that powers the Swagger UI at /api/v1/docs
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI-Driven Development (ADD) API",
    "DESCRIPTION": "Spec-driven delivery platform — workflows, specs, code, approvals.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- ADD Configuration ---

# LLM
# Provider: "ollama" | "litellm" | "claude" | "vertex" (Google Vertex AI, GCP-native)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_ROUTING_CONFIG = os.getenv("LLM_ROUTING_CONFIG", "")
# Vertex AI (used when LLM_PROVIDER=vertex). On GKE, prefer Workload Identity
# over a key file. See src/llm/vertex_provider.py.
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_SPEC_COLLECTION = os.getenv("QDRANT_SPEC_COLLECTION", "spec_embeddings")

# Workflow
MAX_REVISION_CYCLES = int(os.getenv("MAX_REVISION_CYCLES", "3"))
DUPLICATE_SIMILARITY_THRESHOLD = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))
RELATED_SPEC_THRESHOLD = float(os.getenv("RELATED_SPEC_THRESHOLD", "0.65"))
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.30"))
ENABLE_QUERY_EXPANSION = os.getenv("ENABLE_QUERY_EXPANSION", "true").lower() == "true"

# GitHub
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
SPEC_REPO_URL = os.getenv("SPEC_REPO_URL", "")
# GitHub account (user or org) that owns the spec + code repositories.
# Everything downstream derives repo slugs from this, so a new deployment only
# needs to change GITHUB_OWNER (and optionally the repo names below).
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "hubbridge-developer")
# Default target code repo for seeded namespaces. Accepts either a bare repo
# name ("my-app") — combined with GITHUB_OWNER — or a full "owner/name" slug.
CODE_REPO = os.getenv("CODE_REPO", "xspec-demo-app")
SPEC_REPO_NAME = os.getenv("SPEC_REPO_NAME", "xspec-specs")

# Code generation
MAX_CODE_REVISION_CYCLES = int(os.getenv("MAX_CODE_REVISION_CYCLES", "3"))
CODE_CONTEXT_MAX_CHARS = int(os.getenv("CODE_CONTEXT_MAX_CHARS", "4000"))
AUTO_MERGE_ON_APPROVAL = os.getenv("AUTO_MERGE_ON_APPROVAL", "true").lower() == "true"
RUN_GENERATED_TESTS = os.getenv("RUN_GENERATED_TESTS", "true").lower() == "true"
TEST_RUN_TIMEOUT = int(os.getenv("TEST_RUN_TIMEOUT", "180"))

# Encryption
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
