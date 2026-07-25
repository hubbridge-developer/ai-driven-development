# How to Build and Run AIDD POC

Everything runs in Docker Compose — no local Python or Node installation needed.
See `README.md` for what the platform does and how the pipeline works.

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- ~10 GB free disk for images, models, and volumes
- Enough RAM for the local LLMs: `mistral:7b` ≈ 4.5 GB, `codellama:13b` ≈ 8 GB
- Optional: a GitHub Personal Access Token (repo scope) if you want spec/code PRs published

## 1. Configure the environment

```bash
cd /Users/ozgursedefoglu/Projects/ai-driven-development
cp .env.example .env
```

The defaults work out of the box with the local Ollama LLMs. Optional edits:

| Variable | When to set it |
|---|---|
| `GITHUB_PAT` + `SPEC_REPO_URL` | To publish specs/code as GitHub PRs. Without them the GitHub steps fail non-fatally — specs still save to DB + Qdrant |
| `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` | Much better spec/code quality than the local 7B/13B models |
| `LLM_ROUTING_CONFIG=config/llm_routing_ollama.yaml` | Per-agent model routing (mistral for specs, codellama for code) |
| `RUN_GENERATED_TESTS=false` | Skip the pytest run against the target-repo overlay |

## 2. Build and start all services

```bash
docker compose up --build
```

This starts 6 services: **aidd-api** (Django/Daphne, port 8001), **aidd-frontend**
(Vite dev server, port 5173), **postgres**, **redis**, **qdrant**, and **ollama**.

The API container runs its startup sequence automatically:
`migrate → collectstatic → qdrant_create_collection → seed_namespaces → seed_spec_repo → seed_repositories → daphne`.

> Rebuild with `--build` whenever `requirements.txt`, the Dockerfiles, or
> `frontend/package.json` change. Plain `docker compose up` is enough otherwise —
> source directories are volume-mounted.

## 3. Pull the LLM models (first run only)

```bash
docker compose exec ollama ollama pull mistral:7b       # spec agents
docker compose exec ollama ollama pull codellama:13b    # code developer agent
```

Verify with `docker compose exec ollama ollama list`.

## 4. Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| REST API | http://localhost:8001/api/v1/ |
| Django Admin | http://localhost:8001/admin/ |
| Qdrant Dashboard | http://localhost:6333/dashboard |

## 5. Run a workflow

1. Open http://localhost:5173, type a request (or click an example), hit **Start Workflow**
2. Watch the 10-stage stepper and activity log progress in real time
3. At **Approval Gate 1**, review the generated spec → Approve / Reject with feedback
4. After spec approval the code stages run (repo scan → code + tests → code PR)
5. At **Approval Gate 2**, review the generated files, test results, and code PR → Approve / Reject
6. On approval the code PR is squash-merged and the workflow completes

## Common operations

```bash
# Follow API logs
docker compose logs -f aidd-api

# Reset everything in the DB and re-seed
docker compose exec aidd-api python manage.py flush --no-input
docker compose exec aidd-api python manage.py seed_namespaces
docker compose exec aidd-api python manage.py seed_spec_repo
docker compose exec aidd-api python manage.py seed_repositories

# Reset / rebuild the Qdrant vector index
docker compose exec aidd-api python manage.py qdrant_reset
docker compose exec aidd-api python manage.py qdrant_reindex_specs

# One-time: strip tokens from snapshots persisted before the token-leak fix
docker compose exec aidd-api python manage.py scrub_state_tokens

# Stop everything (add -v to also delete DB/Qdrant/Ollama volumes)
docker compose down
```

## Troubleshooting

- **Workflow errors immediately at Spec Discovery** — the Ollama model is
  probably missing; pull it (step 3) and check `docker compose logs ollama`.
- **"GitHub failure" in the activity log** — `GITHUB_PAT` is empty/expired or
  `SPEC_REPO_URL` points to a repo the token can't access. Non-fatal for specs.
- **Port already in use** — 5173, 8001, 5432, 6379, 6333, or 11434 is taken by
  another process; stop it or change the port mapping in `docker-compose.yml`.
- **Frontend loads but no live updates** — check the WebSocket connection in the
  browser dev tools and that redis is healthy (`docker compose ps`).
- **Test Execution reports "error"** — the target repo's dependencies aren't
  importable inside the API container, or the tarball download failed (needs
  `GITHUB_PAT` for private repos). Best-effort by design; set
  `RUN_GENERATED_TESTS=false` to skip.
