# AI-Driven Development (ADD) — Example Flow, Step by Step

This document walks one concrete request through the full 10-stage pipeline and
explains what each step does and which technology drives it.

**The example request** (typed into the UI at http://localhost:5173):

> *Add a password reset feature to the authentication system: users request a
> reset link via email, the link expires after 30 minutes, and used tokens
> cannot be reused.*

**The cast:**

| Piece | Role |
|---|---|
| LangGraph `StateGraph` | Orchestrates the 10 stages; conditional edges decide routing; a checkpointer resumes the graph after human decisions |
| `WorkflowState` (TypedDict) | The single shared state dict every agent reads from and writes to |
| Ollama + LiteLLM | Local LLMs: `mistral:7b` for spec work, `codellama:13b` for code (per-agent routing in `config/llm_routing_ollama.yaml`) |
| Qdrant + sentence-transformers | 768-dim semantic search over previously published specs (`BAAI/bge-base-en-v1.5` embeddings) |
| PostgreSQL | Durable truth: `WorkflowRun` (status + full state snapshot), `GeneratedSpec`, `GeneratedCode`, `Namespace`, `Repository` |
| Django Channels + Redis + Daphne | Pushes every sub-step to the browser over WebSocket in real time |
| GitHub REST API | Spec PR on `xspec-specs`, code PR on `xspec-demo-app`, squash-merge |
| ruff + pytest | Deterministic lint and real test execution of the generated code |

---

## Stage 0 — Start

`POST /api/v1/workflow/start` creates a `WorkflowRun` row (`wf-<12 hex>`,
status `running`) and launches the LangGraph pipeline in a background thread.
The browser opens a WebSocket (`ws/workflow/{id}`) and subscribes; every agent
below reports progress through it (Django Channels → Redis pub/sub → Daphne →
browser). Each sub-step is also appended to `activity_log` inside the state
snapshot, which is why the Agent Activity panel survives page reloads.

---

## Stage 1 — Spec Discovery (`mistral:7b` + Qdrant)

**Question it answers: "Do we already have specs about this?"**

1. **LLM request parsing** — mistral extracts intent, domain keywords, and
   affected areas from the free-text request → e.g. keywords `password`,
   `reset`, `authentication`, `email`.
2. **Namespace resolution** — keywords are matched against `Namespace` rows in
   PostgreSQL → identifies `auth` (this matters later: only namespaces linked
   to a code repository can reach the code stages).
3. **Semantic search** — the request is embedded with sentence-transformers and
   searched against Qdrant twice: against spec-summary vectors and per-section
   vectors. Hits ≥ 0.85 cosine → duplicate warning; ≥ 0.65 → related specs
   (their full content is pulled from PostgreSQL as context for generation).
4. **Classification** — `new` | `update` | `bugfix` → picks the spec template.

**Output:** `identified_namespaces=['auth']`, `related_specs`,
`request_classification='new'`, optional `duplicate_warning`.

---

## Stage 2 — Spec Generation (`mistral:7b` + consistency sub-agent)

**Turns the request into a formal, structured specification.**

1. The LLM receives the request, the top related specs (to avoid
   contradictions), the namespace's `stack_config` (python/django/pytest), and
   a full example spec (small models need one to follow the format). It emits
   an XML-tagged spec with YAML content: `<spec_header>`, `<summary>`,
   `<requirements>`, `<technical_design>`, `<acceptance_criteria>`.
2. A spec ID is allocated from the namespace counter → **`SPEC-AUTH-0002`**.
3. **Consistency Checker sub-agent** (no LLM, zero tokens) — embeds the fresh
   spec and searches Qdrant for spec-level duplicates (≥ 0.85) and per-section
   overlaps (≥ 0.70) against everything published before.
4. Sections containing TBD/TODO/placeholder are flagged `low_confidence`.

**Output:** `generated_spec`, `spec_id`, `consistency_warnings`,
`low_confidence_sections`.

---

## Stage 3 — Spec Validation (deterministic, no LLM)

**Structural gate — is the spec well-formed?** Five checks in order: XML
well-formedness → required sections present → required header fields (parsed
as YAML) → format version == 2 → cross-references exist in the DB.

**Routing (LangGraph conditional edge):** all pass → Approval Gate 1. Any fail
→ back to Spec Generation with the validation errors injected into the prompt,
up to `MAX_REVISION_CYCLES` (3) total attempts, then the workflow errors out.

---

## Stage 4 — Approval Gate 1 (human)

The workflow **suspends**: status becomes `waiting_approval`, the full state is
persisted to PostgreSQL, and the UI shows the parsed spec with warnings.

- **Approve** → the graph is resumed *from the gate* via its checkpointer
  (`resume_from_gate()` seeds a thread with the persisted snapshot as if the
  gate had just run) and routes to Spec Publisher.
- **Reject with feedback** → same mechanism, but routes back to Spec
  Generation with your feedback in the prompt. Discovery is **not** re-run.
- **Cancel** → terminal.

Because the durable state lives in PostgreSQL, this resume works even after a
container restart — you can approve tomorrow.

---

## Stage 5 — Spec Publisher (GitHub + Qdrant indexing)

1. Saves the spec as a `GeneratedSpec` row.
2. GitHub REST API against **`hubbridge-developer/xspec-specs`**: create branch
   `spec/spec-auth-0002` → commit `specs/auth/SPEC-AUTH-0002.md` (rendered
   markdown with collapsible raw XML) → open PR. GitHub failure is non-fatal.
3. Indexes the spec into Qdrant with dual vectors (1 LLM-written summary vector
   + N section vectors, delete-before-upsert) so *future* discoveries find it.

**Output:** `spec_pr_url`, `spec_published`.

---

## Stage 6 — Namespace Resolver (GitHub scan + `mistral:7b` impact analysis)

**Question: "Which repo and which files does this spec touch?"**

1. Loads `Repository` rows for the identified namespaces → `auth` →
   **`hubbridge-developer/xspec-demo-app`** (seeded by `seed_repositories`).
2. **Repo Scanner** — GitHub tree API (recursive) → source file list; detects
   the language; parses `requirements.txt` → dependency map.
3. **Impact Analyzer** — mistral gets the spec + file tree + dependencies and
   returns which files to create/modify and why → e.g. `[modify]
   accounts/views.py`, `[create] accounts/tokens.py`.
4. Builds a bounded context string (`CODE_CONTEXT_MAX_CHARS`) for the next stage.

**Output:** `target_repositories`, `affected_files`, `code_context`.

---

## Stage 7 — Code Developer (`codellama:13b` + 5 sub-agents + verification)

The heavyweight stage. Sub-steps, in order:

1. **Task Planner** — decomposes spec + affected files into ordered tasks with
   dependencies (`T1: Create PasswordResetToken model`, `T2: serializers`, …).
   On a Gate-2 rejection loop, your feedback is injected here so it can reshape
   the plan itself.
2. **Code Writer** — tasks are topologically sorted; for each task it fetches
   the current file content from GitHub (for `modify` targets) and codellama
   returns complete file contents as JSON.
3. **Test Writer** — extracts `<acceptance_criteria>` from the spec and writes
   pytest files covering each criterion.
4. **Syntax + Preservation + Integration Check** — deterministic `compile()`
   on every generated Python file; a preservation check that fetches each
   modified file's original from GitHub and flags any deleted function, class,
   or URL route as critical (small models love to "modify" a file by replacing
   it with only their new feature); and an LLM cross-file review (imports,
   signatures, model fields). Critical findings → one retry of code writing
   with the issues as context.
5. **Lint & Format** — deterministic: `ruff check --fix-only` + `ruff format`
   in a temp workspace. No LLM (an LLM "cleanup" can silently corrupt code).
6. **Test Execution** — downloads the target repo tarball, overlays the
   generated files + tests, and **actually runs pytest** in a subprocess
   (using the demo app's own `DJANGO_SETTINGS_MODULE`, `pytest-django`
   installed, timeout `TEST_RUN_TIMEOUT`).
7. **Test Repair loop** — if tests *fail* (not env errors), the failure output
   is parsed to decide the target: references into the test files → the tests
   are regenerated (broken test code can't be fixed by rewriting the app);
   otherwise the implementation is regenerated ("do NOT modify the tests").
   Up to `MAX_REVISION_CYCLES` (3) rounds. The stage arrives at the gate
   either green or with an honest "still failing" verdict.

**Output:** `generated_files`, `generated_tests`, `integration_issues`,
`test_results`, `implementation_summary`.

---

## Stage 8 — Code Publisher (GitHub Git Data API)

1. Creates branch `code/spec-auth-0002` on the target repo.
2. **Atomic commit** via the low-level Git Data API: create a blob per file →
   build a tree on top of the base tree → create one commit → move the branch
   ref. All files land in a single commit.
3. Opens PR `[SPEC-AUTH-0002] Code implementation` — body contains the
   implementation summary including the test run result. If the tests did not
   pass, the PR is a **draft** titled `[TESTS FAILING] …`: reviewable, but
   unmergeable until a human approves at Gate 2 (approval marks it ready).
4. Saves everything as a `GeneratedCode` row (files, tests, PR references).

**Output:** `code_pr_url`, `code_pr_numbers`, `code_published`.

---

## Stage 9 — Approval Gate 2 (human)

Suspends again: status `waiting_code_approval`. The UI shows the generated
files, tests, test results, and the PR link.

- **Approve** → resume to Code Review Handoff.
- **Reject with feedback** → resume back to Code Developer; your feedback
  reaches both the Task Planner and the Code Writer; a new commit lands on the
  same `code/...` branch and the same PR updates.

---

## Stage 10 — Code Review Handoff (GitHub merge)

Checks each code PR is still open, then **squash-merges** it into the target
repo's `main` with a spec-referenced commit message. Merge failures are
recorded in `merge_results` (`final_status: review-failed`) but don't crash
the workflow. Status → `completed`, final WebSocket notification, and the UI
shows both PR links.

---

## The mechanics underneath (applies to every stage)

**State:** every agent is a function `state → partial state`. LangGraph merges
the returned keys into `WorkflowState` and passes it on. A wrapper
(`_persist_and_notify`) saves the merged snapshot to `WorkflowRun.state_snapshot`
in PostgreSQL and fires a WebSocket event after each stage — that's what moves
the stepper.

**Suspend/resume:** gates don't block a thread. The gate node persists state,
sets a waiting status, and the graph routes to END. The approve/reject REST
endpoint later seeds the graph's checkpointer with the saved snapshot *at the
gate node* and re-invokes it — the graph continues as if it had never stopped.

**Real-time updates:** agent (background thread) → `channel_layer.group_send`
→ Redis pub/sub → Daphne's async loop → WebSocket → React. Polling (3s) is
the fallback; `activity_log` in the snapshot replays history on page reload.

**LLM abstraction:** every model call goes through `call_llm()` (LiteLLM), so
`ollama/mistral:7b`, `ollama/codellama:13b`, or `claude-*` are interchangeable
via `LLM_PROVIDER` and the per-agent routing YAML — no agent code changes.

**Trust boundaries:** everything the LLM produces is checked by something
deterministic before it reaches a human or a repo: XML validation for specs,
`compile()`/ruff/pytest for code, and two human gates for judgment.
