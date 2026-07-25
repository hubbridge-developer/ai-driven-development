# AI-Driven Development (ADD) — Spec-Driven Delivery Platform

> Full build/run instructions, common operations, and troubleshooting: **[HOW_TO_RUN.md](HOW_TO_RUN.md)**
> A worked example of one request through all 10 stages, with the technology behind each: **[EXAMPLE_FLOW.md](EXAMPLE_FLOW.md)**

## Run the POC

```bash
cd /Users/ozgursedefoglu/Projects/ai-driven-development
cp .env.example .env        # first run only — adjust GITHUB_PAT / SPEC_REPO_URL if publishing
docker compose up --build
```

First run: Ollama needs to pull the LLM models (may take a few minutes):

```bash
docker compose exec ollama ollama pull mistral:7b       # spec agents
docker compose exec ollama ollama pull codellama:13b    # code developer agent
```

## Access

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8001/api/v1/ |
| **API Docs (Swagger UI)** | **http://localhost:8001/api/v1/docs** |
| API Docs (ReDoc) | http://localhost:8001/api/v1/redoc |
| Django Admin | http://localhost:8001/admin/ |
| Qdrant Dashboard | http://localhost:6333/dashboard |

## Flow

1. Open http://localhost:5173
2. Type a request (or click an example) and hit **"Start Workflow"**
3. Watch the pipeline stepper progress through each stage with animated transitions and a live activity log
4. At **"Approval Gate 1"** the full spec appears with Approve/Reject buttons
   - **Approve** → spec saved to DB + indexed into Qdrant + spec PR opened on GitHub, then the code stages start
   - **Reject** with feedback → spec regenerates incorporating your feedback
5. The code stages run: target repo resolution → code + test generation → code PR opened on the target repo
6. At **"Approval Gate 2"** the generated files, tests, and code PR appear for review
   - **Approve** → code PR is squash-merged into the target repo
   - **Reject** with feedback → code regenerates and a new review round starts
7. On completion, **"View PR"** links appear for both the spec PR and the code PR

---

## Pipeline (10-Stage LangGraph Workflow)

```
                     ┌─────── invalid (up to 3 total attempts) ────────┐
                     ↓                                                 |
User Request → Spec Discovery → Spec Generation → Spec Validator → Approval Gate 1 → Spec Publisher
                                      ↑                                |                   |
                                      └──── rejected (with feedback) ──┘                   |
                                                                                  approved |
                                                                                           ↓
     Code Review Handoff ← Approval Gate 2 ← Code Publisher ← Code Developer ← Namespace Resolver
                                 |                                  ↑
                                 └───── rejected (with feedback) ───┘
```

The pipeline is implemented as a LangGraph StateGraph (`src/graph/workflow.py`) with conditional edges (`src/graph/edges.py`) and a shared `WorkflowState` TypedDict (`src/graph/state.py`). Each agent node is wrapped with `_persist_and_notify()` which saves the current stage to PostgreSQL and sends a WebSocket message after each agent completes, enabling real-time frontend stepper updates. Agents also emit granular sub-step events via `notify_sub_step()`, which are appended to a persistent `activity_log` in the workflow state so the frontend Activity Log survives page reloads.

Approval decisions resume the **same graph** via its checkpointer: `resume_from_gate()` seeds a thread with the persisted state snapshot as if the gate node had just run, and the graph's conditional edges route onward (approved → next stage, rejected → revision loop). No stage sequencing exists outside the graph, and rejections never re-run earlier stages such as spec discovery. Durable state lives in PostgreSQL, so resumes survive process restarts.

---

### Agent 1 — Spec Discovery (`src/agents/spec_discovery.py`)

**Purpose:** Search the spec repository for existing specs related to the user's request.

- Parses user request via LLM to extract intent, domain keywords, affected system areas
- Resolves namespace(s) from PostgreSQL (matches keywords against namespace name/description)
- Dual-vector semantic search in Qdrant (summary vectors + section vectors)
- Duplicate detection (≥ 0.85 cosine similarity threshold) — informational, non-blocking
- Related spec retrieval (≥ 0.65) with full content fetched from DB for downstream context
- Optional LLM query expansion for terse or ambiguous requests (configurable via `ENABLE_QUERY_EXPANSION`)
- Request classification: `new` | `update` | `bugfix`

> **Note:** Classification affects the spec type label (feature/change-request/bugfix) but there is no special logic to load and modify an existing spec for "update" — all classifications generate a new spec from scratch. Full update/versioning is not implemented in this POC.

**Key Outputs:** `related_specs`, `identified_namespaces`, `request_classification`, `extends_spec`, `duplicate_warning`

---

### Agent 2 — Spec Generation (`src/agents/spec_generator.py`)

**Purpose:** Generate a new specification using LLM based on user request and discovery context.

- Generates structured XML-tagged spec with YAML inner content via LLM
- System prompt includes a full concrete example spec to help small models follow the format
- Template selection based on classification: new→feature, update→change-request, bugfix→bugfix
- Injects related specs (top 3) as context so LLM can avoid contradictions
- Injects `stack_config` (language, framework, test_framework, build_tool) from namespace
- Handles revision loops:
  - Rejection feedback from approval gate → included in prompt for regeneration
  - Validation errors from spec_validator → included in prompt for retry
- Auto-assigns spec IDs following `SPEC-{NAMESPACE}-{SEQUENCE}` convention (via `Namespace.allocate_spec_id()`)
- Detects low-confidence sections by scanning for indicators: TBD, TODO, placeholder, estimated, etc.

#### Sub-Agent: Consistency Checker (`src/agents/sub_agents/consistency_checker.py`)

- Runs after spec generation, before validation
- Uses sentence-transformers + Qdrant search (no LLM, zero token cost)
- Embeds the generated spec's `<summary>` section → searches Qdrant for spec-level duplicates (≥ 0.85)
- Embeds each section (requirements, technical_design, acceptance_criteria) → searches Qdrant for section-level overlaps (≥ 0.70)
- Source of truth is Qdrant, not PostgreSQL — works even if DB records are deleted
- Returns: `duplicate_warning` (overrides discovery's warning if found), `consistency_warnings` list
- All warnings are displayed in the frontend SpecViewer component

**Key Outputs:** `generated_spec`, `spec_id`, `low_confidence_sections`, `consistency_warnings`, `duplicate_warning`

---

### Agent 2.5 — Spec Validator (`src/agents/spec_validator.py`)

**Purpose:** Structural validation gate — fully deterministic, no LLM, zero token cost.

- Cleans LLM output artifacts first: strips markdown fences, preamble text, trailing text
- 5 validation checks (in order):
  1. **XML well-formedness** — all tags properly opened, closed, and nested
  2. **Required sections present** — spec_header, summary, requirements, technical_design, acceptance_criteria
  3. **Required header fields** — format_version, spec_id, namespace, type (parsed as YAML)
  4. **Format version match** — must be 2 (`EXPECTED_FORMAT_VERSION`)
  5. **Cross-reference validation** — checks dependency spec IDs exist in DB (non-blocking warning)
- Retry logic: on failure, increments `spec_validation_retry_count`. The edge router (`route_after_validator`) checks: if `retry_count < MAX_REVISION_CYCLES` (default 3), routes back to spec_generator with validation errors as context. Otherwise routes to END (error). Total: up to 3 attempts (1 initial + 2 retries).

**Key Outputs:** `spec_validation_results`, `spec_validation_retry_count`, `spec_format_version`

---

### Approval Gate 1 (`src/approval/gate.py`)

**Purpose:** Pause the workflow for human review of the generated specification.

- Sets `WorkflowRun.status` to `WAITING_APPROVAL` in PostgreSQL
- Persists full LangGraph state to `WorkflowRun.state_snapshot`
- Sends WebSocket notification to frontend (spec ready for review)
- Outcomes:
  - **Approve** → graph resumes from the gate to spec_publisher and continues through the code stages up to Approval Gate 2
  - **Reject** with feedback → graph resumes from the gate back to spec_generator (spec discovery is **not** re-run)
  - **Cancel** → permanently cancels the workflow
  - **Pending** → workflow suspended indefinitely, resumable via REST API at any time

---

### Agent 3 — Spec Publisher (`src/agents/spec_publisher.py`)

**Purpose:** Publish the approved spec to GitHub and index into Qdrant.

Full flow (6 steps):

1. Save spec to `GeneratedSpec` model in PostgreSQL
2. Publish to GitHub via REST API (`src/github/service.py`):
   - Reads `SpecRepoConfig` from DB (falls back to `SPEC_REPO_URL` env var)
   - Gets base branch SHA (auto-initializes empty repos with README)
   - Creates feature branch: `spec/{spec-id-lowercase}`
   - Renders spec as markdown file (tables, code blocks, collapsible raw XML)
   - Commits to: `specs/{namespace}/{SPEC_ID}.md`
   - Opens pull request with spec summary as PR body
   - GitHub failure is non-fatal — spec still saves to DB and Qdrant
3. Generate LLM summary for Qdrant indexing (fallback: first 500 chars if LLM fails)
4. Index into Qdrant with dual vectors:
   - 1 summary vector (LLM-summarized content, 768-dim)
   - N section vectors (one per XML section: summary, requirements, technical_design, etc.)
   - Delete-before-upsert pattern to prevent stale vectors
   - Qdrant indexing is non-fatal
5. Update `WorkflowRun` status to `COMPLETED`
6. Send WebSocket notification with PR URL

**Key Outputs:** `spec_published`, `spec_pr_url`, `spec_pr_number`

---

### Agent 4 — Namespace Resolver (`src/agents/namespace_resolver.py`)

**Purpose:** Map the approved spec to target code repositories and build code context for generation.

- Loads `Repository` records for the identified namespaces from PostgreSQL (seeded by `seed_repositories`)
- **Repo Scanner** (`sub_agents/repo_scanner.py`) — fetches the recursive file tree via GitHub API, auto-detects the primary language, parses dependency files (`requirements.txt`, `package.json`)
- **Impact Analyzer** (`sub_agents/impact_analyzer.py`) — LLM analyzes spec vs. repo structure to identify which files to create/modify and why
- Builds a bounded code-context string for the Code Developer (`CODE_CONTEXT_MAX_CHARS`, default 4000)

> **POC limitation:** only the first target repository is scanned and used for code generation.

**Key Outputs:** `target_repositories`, `affected_files`, `code_context`, `impact_summary`

---

### Agent 5 — Code Developer (`src/agents/code_developer.py`)

**Purpose:** Orchestrate 5 sub-agents to implement the spec as code. Uses `codellama:13b` by default (see `config/llm_routing_ollama.yaml`).

Sub-steps (in order):

1. **Task Planner** (`sub_agents/task_planner.py`) — LLM decomposes spec + affected files into ordered implementation tasks with dependencies. On a rejection revision loop, the reviewer feedback is injected so it can reshape the task breakdown
2. **Code Writer** (`sub_agents/code_writer.py`) — per task (topologically sorted): fetches existing file content from GitHub for "modify" targets, then LLM generates complete file contents; later tasks override earlier ones for the same path
3. **Test Writer** (`sub_agents/test_writer.py`) — extracts `<acceptance_criteria>` from the spec, LLM generates unit/integration tests. If it produces none, it's retried once; still none → `test_results` is set to `error` ("code is UNVERIFIED") so the gap is loud at the approval gate
4. **Syntax + Preservation + Integration Check** — deterministic `compile()` syntax check on every generated Python file, plus a **preservation check** (`sub_agents/code_verifier.py`): for each "modify" file the original is fetched from GitHub and any deleted top-level function/class or URL route is a critical issue (LLMs asked for "the complete file" often return only their new feature). Plus LLM cross-file review (`sub_agents/integration_checker.py`): unresolved imports, mismatched signatures, missing model fields, circular deps. Critical issues → code writing retried once with the issues injected as context
5. **Lint Formatter** (`sub_agents/lint_formatter.py`) — deterministic cleanup: `ruff check --fix-only` + `ruff format` on Python files (basic whitespace/EOF cleanup otherwise). No LLM involved
6. **Test Execution** (`sub_agents/code_verifier.py`) — downloads the target repo tarball, overlays the generated files + tests, and runs `pytest` in a subprocess (timeout `TEST_RUN_TIMEOUT`). Results (passed/failed/error) are recorded in `test_results` and shown in the implementation summary and code PR. Disable with `RUN_GENERATED_TESTS=false`
7. **Test Repair loop** — on real test failures (not env errors), up to `MAX_REVISION_CYCLES` repair rounds. The failure output is parsed to decide the target: `file.py:line` references pointing into the test files → the **tests** are regenerated with the failure as context; otherwise the **implementation** is regenerated ("do NOT modify the tests")

**Key Outputs:** `implementation_tasks`, `generated_files`, `generated_tests`, `integration_issues`, `implementation_summary`, `test_results`

---

### Agent 6 — Code Publisher (`src/agents/code_publisher.py`)

**Purpose:** Push generated code + tests to target repositories and open PRs.

- Creates feature branch `code/{spec-id-lowercase}` per target repo
- **Atomic multi-file commit** via the Git Data API: create blobs → create tree → create commit → update ref (single commit for all files)
- Opens PR titled `[SPEC-ID] Code implementation` with the implementation summary and file list as body
- **If tests did not pass** (failed/error/unverified), the PR is opened as a **GitHub draft** titled `[TESTS FAILING] …` — reviewable but unmergeable. Approving at Gate 2 is the explicit human override: the handoff marks it ready (GraphQL) and merges
- Saves files, tests, summary, and PR references to the `GeneratedCode` model
- Per-repo GitHub failures are non-fatal (logged, repo skipped)

**Key Outputs:** `code_published`, `code_pr_url`, `code_pr_numbers`

---

### Approval Gate 2 (`src/approval/gate.py` — `code_approval_gate_node`)

**Purpose:** Pause the workflow for human review of the generated code.

- Sets `WorkflowRun.status` to `WAITING_CODE_APPROVAL` and persists full state
- Sends WebSocket notification with file/test counts and the code PR URL
- Outcomes:
  - **Approve** → resumes to Code Review Handoff (merge)
  - **Reject** with feedback → re-runs Code Developer → Code Publisher → gate (revision loop)
  - **Cancel** → permanently cancels the workflow

---

### Agent 7 — Code Review Handoff (`src/agents/code_review_handoff.py`)

**Purpose:** Final stage — merge approved code PRs and finalize the workflow.

- Checks each code PR's state via GitHub API
- **Squash-merges** open PRs (`merge_method: squash`) with a spec-referenced commit message
- Merge failures are recorded in `merge_results` but are non-fatal
- Sets `WorkflowRun` status to `COMPLETED` and sends the final WebSocket notification

**Key Outputs:** `merge_results`, `final_status`

---

## Django Backend

### Models (`src/add_api/models.py`)

| Model | Purpose |
|---|---|
| **Namespace** | Business domain (auth, payments...) with `stack_config` JSON and spec sequence counter. `allocate_spec_id()` generates `SPEC-{NS}-{SEQ}` and auto-increments. |
| **Repository** | Target code repo linked to a namespace (repo_slug, paths, encrypted_token). Not actively used in this POC — placeholder for code generation stages. |
| **WorkflowRun** | Tracks workflow execution: status, current_agent, state_snapshot (full LangGraph state serialized as JSON), token_usage, error. Status: running/waiting_approval/waiting_code_approval/completed/failed/error/cancelled. |
| **GeneratedSpec** | Published specs with spec_id, namespace, content, version, indexed_at (Qdrant timestamp) |
| **GeneratedCode** | Generated code output per workflow: files + tests (JSON), implementation_summary, code PR URL/numbers, version |
| **SpecRepoConfig** | GitHub spec repository config: spec_repo_url, branch, active flag. Auto-seeded from `SPEC_REPO_URL` env var on startup. |

### REST API (`src/add_api/views.py`, `urls.py`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/workflow/start` | Start new workflow (runs pipeline in background thread) |
| GET | `/api/v1/workflow/{id}` | Get workflow status, current_agent, state_snapshot |
| GET | `/api/v1/workflow/{id}/spec` | Get spec content, validation results, discovery results, consistency warnings, PR URL |
| POST | `/api/v1/workflow/{id}/approve` | Approve spec at Gate 1, resumes pipeline through publisher + code stages |
| POST | `/api/v1/workflow/{id}/reject` | Reject spec with feedback, regenerates spec |
| GET | `/api/v1/workflow/{id}/code` | Get generated files, tests, implementation summary, code PR info |
| POST | `/api/v1/workflow/{id}/approve-code` | Approve code at Gate 2, resumes to review handoff (merge) |
| POST | `/api/v1/workflow/{id}/reject-code` | Reject code with feedback, re-runs code developer → publisher |
| POST | `/api/v1/workflow/{id}/cancel` | Cancel workflow permanently (at either gate) |
| GET | `/api/v1/workflows` | List workflows with optional `?status=` filter (max 50) |
| GET | `/api/v1/specs` | List all generated specs (max 100) |
| POST | `/api/v1/specs/search` | Semantic search across specs via Qdrant |
| CRUD | `/api/v1/namespaces/` | Full CRUD for namespace management (ModelViewSet) |

### WebSocket (`src/add_api/consumers.py`)

- Endpoint: `ws/workflow/{workflow_id}`
- Broadcasts: agent transitions (after each stage), sub-step progress, approval notifications, completion/error events
- Uses Django Channels + Redis channel layer (pub/sub)
- Each agent completion triggers a DB persist + WS message via `_persist_and_notify` wrapper
- Sub-step reporting via `notify_sub_step()` for granular progress updates
- Frontend uses ReconnectingWebSocket for automatic reconnection

### Management Commands

| Command | Purpose |
|---|---|
| `seed_namespaces` | Seeds 4 default namespaces: auth, payments, notifications, user-management |
| `seed_spec_repo` | Creates SpecRepoConfig from `SPEC_REPO_URL` env var |
| `seed_repositories` | Links namespaces (auth, user-management) to target code repos for code generation |
| `qdrant_create_collection` | Creates spec_embeddings collection in Qdrant (non-fatal if Qdrant unavailable) |
| `qdrant_reset` | Deletes and recreates Qdrant collection |
| `qdrant_reindex_specs` | Re-indexes all specs from DB into Qdrant |

### Docker Startup Sequence

```
migrate → collectstatic → qdrant_create_collection → seed_namespaces → seed_spec_repo → seed_repositories → daphne
```

---

## Technologies

| Layer | Technology | Purpose |
|---|---|---|
| API Framework | Django 5.1 + DRF 3.15.2 | REST API, ORM, admin panel |
| Agent Orchestration | LangGraph 0.2.50 | StateGraph with conditional edges, shared TypedDict state |
| LLM Abstraction | LiteLLM 1.81.15 | Provider-agnostic: Ollama (default), Claude, 100+ providers. Switch via `LLM_PROVIDER` env var. Per-agent model routing support. |
| Local LLM | Ollama (mistral:7b + codellama:13b) | Default LLMs for POC — mistral:7b for spec agents, codellama:13b for code generation. Runs as Docker service on port 11434. |
| Vector Search | Qdrant | Dual-vector semantic search (768-dim, cosine similarity) |
| Embeddings | sentence-transformers (BAAI/bge-base-en-v1.5) | 768-dim vectors for spec indexing and search. Used by discovery, consistency checker, and publisher. |
| Database | PostgreSQL 16 | Authoritative state store: models, workflow state, generated specs, namespace config. |
| Real-Time | Django Channels + Daphne + Redis | WebSocket per-workflow updates. Redis as channel layer broker between background threads and WS connections. |
| Static Files | WhiteNoise | Serves Django admin CSS/JS via ASGI (no nginx needed) |
| GitHub Integration | GitHub REST API (via requests) | Create branches, commit spec markdown, atomic code commits (Git Data API), open + squash-merge PRs |
| Frontend | React 18 + TypeScript + MUI v5 + Vite | 3-page dashboard with real-time stepper animation and activity log |
| Container | Docker Compose | 6 services: api, frontend, postgres, redis, qdrant, ollama |

---

## React Frontend (`frontend/`)

3 Pages, 5 Components, WebSocket hook, API client, TypeScript types.

| Page | Features |
|---|---|
| **New Spec** (`/`) | Text input, clickable example requests, navigates to detail on start |
| **Workflows** (`/workflows`) | Status-filtered workflow table, auto-refresh every 5s, click row to detail |
| **Workflow Detail** (`/workflow/{id}`) | Two-column layout — see below |

### Workflow Detail Layout

**Left Panel:**
- Pipeline stepper (10 stages, animated 800ms transitions, color-coded icons: green check=done, blue dot=active, hourglass=waiting, red=error, gray=future)
- Sub-step progress indicators per stage (green CheckCircle=done, ArrowRight=active, gray dot=future)
- Running status indicator with current stage name
- Error display
- ActivityLog: live scrolling log of every sub-step event (agent, detail, LLM model, timestamp), persisted in workflow state so it survives page reloads
- Discovery Results panel: classification chip, extends_spec, namespace chips, related specs with similarity scores and match types

**Right Panel:**
- SpecViewer: parsed XML sections displayed individually, spec_header as table, duplicate warnings (amber alert), consistency warnings (amber alert), low-confidence section highlights, raw spec collapsible
- ApprovalDialog: approve button + reject with feedback textarea + cancel spec button (Gate 1)
- CodeApprovalDialog: implementation summary, generated files/tests, code PR link, approve/reject with feedback (Gate 2)
- PR links: "View PR #N" buttons for the spec PR and code PR (link to GitHub)
- Completion alert: confirms save to DB + Qdrant indexing + merge results

**Updates via:** WebSocket (instant) + polling (3s while running)

---

## Django Channels + Daphne + Redis — How They Work Together

### The Problem

Standard Django uses HTTP: client sends request → server responds → connection closed. This is request-response only — the server can never push data to the client on its own.

ADD needs the server to push updates to the browser in real-time:
- "Spec Discovery completed, moving to Spec Generation..."
- "Spec Generation in progress..."
- "Approval needed!"

That requires **WebSocket** — a persistent, bidirectional connection.

### The Three Pieces

```
Browser (React)                   Daphne                     Redis
    |                               |                          |
    |--- WS connect --------------->|                          |
    |    /ws/workflow/wf-abc123     |                          |
    |                               |-- subscribe ------------>|
    |                               |   group: workflow_wf-abc |
    |                               |                          |
    |   (meanwhile, agent completes in background thread       |
    |    and _persist_and_notify sends via channel layer...)   |
    |                               |                          |
    |                               |<-- message --------------|
    |                               |   "stage completed"      |
    |<-- JSON push -----------------|                          |
    |   {current_agent: "..."}      |                          |
```

- **Daphne** — the ASGI server (replaces gunicorn/uvicorn). Handles both HTTP and WebSocket connections on the same port (8001).
- **Django Channels** — the framework layer. Extends Django to handle WebSocket connections. `WorkflowConsumer` handles connect/disconnect, forwards messages to browser. `channel_layer.group_send()` lets any Python code (even background threads) push to WS clients.
- **Redis** — the message broker between processes. Background thread (agent) → Redis → Daphne async loop → WebSocket → Browser. In this POC, Redis is used ONLY for the channel layer (WebSocket message routing). No caching, no session storage, no LLM response caching.

---

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DEBUG` | Debug mode (default: True) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `LLM_PROVIDER` | `"ollama"` (default) \| `"litellm"` \| `"claude"` |
| `LLM_ROUTING_CONFIG` | Path to per-agent model routing YAML |
| `ANTHROPIC_API_KEY` | Required when LLM_PROVIDER is "litellm" or "claude" |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant connection (default: qdrant:6333) |
| `QDRANT_SPEC_COLLECTION` | Collection name (default: spec_embeddings) |
| `GITHUB_PAT` | GitHub Personal Access Token (repo scope) |
| `SPEC_REPO_URL` | GitHub repo URL for spec publishing |
| `MAX_REVISION_CYCLES` | Max validation retries (default: 3) |
| `CODE_CONTEXT_MAX_CHARS` | Max size of the code context passed to the Code Developer (default: 4000) |
| `RUN_GENERATED_TESTS` | Execute generated tests with pytest against a target-repo overlay (default: true) |
| `TEST_RUN_TIMEOUT` | Timeout in seconds for the generated-test run (default: 180) |
| `DUPLICATE_SIMILARITY_THRESHOLD` | Qdrant duplicate detection threshold (default: 0.85) |
| `RELATED_SPEC_THRESHOLD` | Related spec inclusion threshold (default: 0.65) |
| `RELEVANCE_THRESHOLD` | Minimum score for any search result (default: 0.30) |
| `ENABLE_QUERY_EXPANSION` | LLM query expansion in discovery (default: true) |
| `ENCRYPTION_KEY` | For sensitive data encryption (not used in POC) |

---

## File Structure

```
poc/
├── docker-compose.yml                          # 6 services: api, frontend, postgres, redis, qdrant, ollama
├── Dockerfile                                  # Python 3.12 slim, pip install, bge-base-en-v1.5 pre-downloaded
├── requirements.txt                            # 19 dependencies
├── manage.py
├── .env                                        # All configuration
├── config/
│   └── llm_routing_ollama.yaml                 # Per-agent model routing (mistral:7b)
│
├── add_project/                              # Django project config
│   ├── settings.py                             # All ADD settings from env vars
│   ├── urls.py
│   ├── asgi.py                                 # Channels routing (HTTP + WebSocket)
│   └── wsgi.py
│
├── src/
│   ├── agents/
│   │   ├── spec_discovery.py                   # Agent 1: LLM parsing + Qdrant search
│   │   ├── spec_generator.py                   # Agent 2: LLM spec generation
│   │   ├── spec_validator.py                   # Agent 2.5: deterministic validation
│   │   ├── spec_publisher.py                   # Agent 3: DB + GitHub + Qdrant
│   │   ├── namespace_resolver.py               # Agent 4: target repos + code context
│   │   ├── code_developer.py                   # Agent 5: orchestrates 5 code sub-agents
│   │   ├── code_publisher.py                   # Agent 6: atomic commit + code PR
│   │   ├── code_review_handoff.py              # Agent 7: squash-merge approved PRs
│   │   └── sub_agents/
│   │       ├── consistency_checker.py          # Qdrant-based duplicate/overlap detection
│   │       ├── repo_scanner.py                 # GitHub file tree + dependency parsing
│   │       ├── impact_analyzer.py              # LLM: which files to create/modify
│   │       ├── task_planner.py                 # LLM: spec → ordered implementation tasks
│   │       ├── code_writer.py                  # LLM: per-task code generation
│   │       ├── test_writer.py                  # LLM: tests from acceptance criteria
│   │       ├── integration_checker.py          # LLM: cross-file consistency review
│   │       ├── code_verifier.py                # Deterministic: syntax check + pytest test run
│   │       └── lint_formatter.py               # Deterministic: ruff autofix + format
│   │
│   ├── approval/
│   │   └── gate.py                             # Approval Gates 1 & 2: pause/resume/cancel workflow
│   │
│   ├── graph/
│   │   ├── state.py                            # WorkflowState TypedDict
│   │   ├── edges.py                            # Conditional routing: route_after_validator, route_after_approval_gate
│   │   └── workflow.py                         # LangGraph StateGraph builder + _persist_and_notify wrapper
│   │
│   ├── llm/
│   │   └── provider.py                         # LiteLLM abstraction: call_llm(), provider routing, per-agent overrides
│   │
│   ├── qdrant_client/
│   │   └── service.py                          # Qdrant operations: create_collection, index_spec, search_specs, embed_text
│   │
│   ├── github/
│   │   └── service.py                          # GitHub REST API: create_branch, commit_file, create_pull_request
│   │
│   └── add_api/
│       ├── models.py                           # 6 models: Namespace, Repository, WorkflowRun, GeneratedSpec, GeneratedCode, SpecRepoConfig
│       ├── views.py                            # REST endpoints + _run_pipeline/_resume_pipeline helpers
│       ├── serializers.py                      # DRF serializers
│       ├── urls.py                             # URL routing
│       ├── consumers.py                        # WebSocket consumer
│       ├── routing.py                          # Channels URL routing
│       ├── admin.py                            # Django admin registration
│       └── management/commands/
│           ├── seed_namespaces.py              # Seeds 4 default namespaces
│           ├── seed_spec_repo.py               # Seeds SpecRepoConfig from env
│           ├── seed_repositories.py            # Links namespaces to target code repos
│           ├── qdrant_create_collection.py     # Creates Qdrant collection
│           ├── qdrant_reset.py                 # Deletes and recreates Qdrant collection
│           └── qdrant_reindex_specs.py         # Re-indexes all specs into Qdrant
│
└── frontend/
    ├── Dockerfile                              # Node 20, Vite dev server
    ├── package.json                            # React 18, MUI v5, axios, react-router-dom, reconnecting-websocket
    ├── vite.config.ts                          # Proxy /api → add-api:8001, /ws → add-api:8001
    └── src/
        ├── App.tsx                             # MUI theme, React Router, NavBar
        ├── main.tsx                            # Entry point
        ├── types/index.ts                      # TypeScript interfaces + PIPELINE_STAGES constant
        ├── api/client.ts                       # Axios client: startWorkflow, getWorkflow, approve, reject, cancel, etc.
        ├── hooks/useWorkflowSocket.ts          # ReconnectingWebSocket hook
        ├── pages/
        │   ├── WorkflowStartPage.tsx           # New spec input page
        │   ├── WorkflowListPage.tsx            # Workflow list with filters
        │   └── WorkflowDetailPage.tsx          # Detail page: stepper, spec viewer, approval, PR link
        └── components/
            ├── PipelineStepper.tsx              # Animated 10-step vertical stepper with sub-step tracking
            ├── ActivityLog.tsx                  # Live sub-step event log (agent, detail, model, timestamp)
            ├── SpecViewer.tsx                   # Parsed XML viewer with warnings
            ├── ApprovalDialog.tsx               # Gate 1: approve/reject/cancel with feedback
            └── CodeApprovalDialog.tsx           # Gate 2: code review approve/reject with feedback
```

---

## What's NOT in this POC

### Features not implemented

- Spec versioning — "update" classification generates a new spec, doesn't modify existing
- LLM response caching — Redis is only used for WebSocket channel layer, not as LLM cache
- Per-repo encrypted tokens — Fernet encryption model exists but not used
- Guardrails — no prompt injection detection or input sanitization
- Elasticsearch / Kibana — no audit logging or observability dashboards
- MCP servers — not implemented
- Streamlit dashboard — React dashboard used instead

### Limitations

- **LLM quality** — mistral:7b / codellama:13b produce reasonable but imperfect results. Switching to Claude (`LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY`) significantly improves quality.
- **Duplicate detection** — embedding similarity between different LLM-generated texts for the same request often scores below the 0.85 threshold. The consistency checker (spec-vs-spec comparison) is more reliable than discovery's request-vs-summary comparison.
- **Namespace resolution** — small LLMs inconsistently map requests to namespaces
- **Pipeline runs in a background thread** (`threading.Thread`), not a task queue (Celery)
- **Single target repo** — namespace resolution collects all repos but only the first is scanned and implemented against
- **Test execution is best-effort** — generated tests run inside the API container against a tarball overlay of the target repo, so they only work if the target repo's dependencies are importable there (true for the Django demo app). Failures are reported, not blocking
- **Code PR branch reuse** — the code branch name is derived from the spec ID, so a rejected+regenerated implementation commits to the same branch/PR
