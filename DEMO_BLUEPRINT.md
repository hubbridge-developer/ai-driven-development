# AI-Driven Development (ADD) — Demo Blueprint

> Audience: **technical** (engineers, architects). Goal: show that ADD turns a
> plain-English request into a **reviewed, tested pull request** through a
> transparent, human-approved pipeline — and that the engineering underneath is
> real, not a wrapper around a chat prompt.
>
> Golden rule for a tech crowd: **show, don't tell.** Demo early, explain after
> they're already impressed. Respect their intelligence — name the limitations
> before they do.

---

## 0. The one-liner (say this first, verbatim)

> "ADD takes one sentence of intent and produces a spec, code, and tests — each
> reviewed by a human at a gate — and opens the pull requests for you. It's not
> autocomplete. It's a **spec-driven, multi-agent pipeline** with memory,
> validation, and a GitOps deployment. Let me show you, then I'll open the hood."

---

## 1. Run-of-show (target ~25 min + Q&A)

| # | Segment | Time | Purpose |
|---|---|---|---|
| 1 | Hook + one-liner | 2 min | Frame it; kill the "another Copilot?" reflex |
| 2 | **Live demo** | 10 min | The wow — one sentence → merged-ready PRs |
| 3 | Architecture deep-dive | 7 min | Earn the engineers' respect |
| 4 | Differentiators | 3 min | Why not Copilot/Cursor/an autonomous agent |
| 5 | Deployment & ops | 3 min | Show it's real infra, not a laptop demo |
| 6 | Q&A | open | Use the arsenal in §7 |

Keep architecture **after** the demo. If time runs short, cut §4 before §3.

---

## 2. The hook (2 min)

Pick ONE opener:

- **Contrast:** "Copilot autocompletes a line. An autonomous agent YOLOs a
  branch and hopes. ADD does neither — it works the way a *good team* works: a
  spec, a review, tests, a second review, then merge. The difference is
  **governance**, not just generation."
- **Pain:** "The bottleneck in software isn't typing code — it's alignment,
  review, and keeping specs and code in sync. ADD automates the *pipeline
  around* the code, with humans at the decision points."

Then the one-liner (§0) and straight into the demo.

---

## 3. Live demo script (10 min)

**Setup before they walk in:**
- App open at the **login page** (looks polished, sets the tone).
- A second browser tab on the **target GitHub repo** (`xspec-demo-app`) Pull
  Requests page.
- A third tab on **Swagger** (`/api/v1/docs`) — you'll show it at the end.
- Provider = **Vertex/Gemini** (better quality than the free models).

**The prompt to use (public endpoint → clean, testable):**
> **Let users check if a username is already taken.**

### Beat-by-beat

1. **Login** — "First, sign in." Click *Use demo credentials* → Sign in.
   *(One line: "cosmetic gate for the demo — real SSO is a config, not a
   rebuild.")* Don't oversell it.

2. **Type the sentence.** "That's the entire input. One sentence." Submit.

3. **Spec Discovery** — narrate what's happening on screen:
   - "It parses intent, then searches a **vector database (Qdrant)** of every
     prior spec — by *content* and by *summary* — to find related work and
     **detect duplicates**. This is the system's memory. It won't reinvent
     something you already specced."

4. **Spec Generation → Validation** — "It writes a structured spec, then runs
   **deterministic validators** — XML well-formedness, required sections,
   cross-references. Not 'the LLM says it's fine' — actual checks."

5. **Approval Gate #1 (spec).** ⏸ "Here's the first human gate. The AI proposes;
   a person decides. Nothing proceeds without approval." — Approve.
   - Switch to GitHub tab: **a spec PR was opened.** "The spec is now versioned
     in git. The spec is the source of truth, not a throwaway prompt."

6. **Namespace Resolver → Code Developer** — this is the meat:
   - "It scans the target repo, does **impact analysis** (which files change),
     then a sub-agent pipeline: **plan tasks → write code → write tests →
     integration check → lint → run tests → repair.**"
   - Call out the **preservation check**: "A deterministic guard that rejects
     edits which would *delete* existing routes or functions. This is how we
     stop an LLM from 'helpfully' rewriting your file and dropping things."

7. **Approval Gate #2 (code).** ⏸ "Second gate. Tests ran. If they fail, the PR
   is opened as a **draft** — the system refuses to present unverified code as
   done. That's a feature." — Approve.
   - GitHub tab: **the code PR** with the new endpoint + tests.

8. **Cost + time.** Point at the header chips: "Every stage tracks its own time
   and LLM cost. Full transparency on what the AI spent."

9. **Swagger tab.** "And the new endpoint is live in the API docs." Optional:
   hit *Try it out*.

**Close the demo:** "One sentence in. A versioned spec, working code, tests, and
two pull requests out — every step reviewable, every decision gated by a human."

---

## 4. Architecture deep-dive (7 min) — for the engineers

Draw or show this. Keep it to the **mechanism**, not buzzwords.

**The pipeline — a LangGraph state machine, 10 stages:**

```
spec_discovery → spec_generator → spec_validator → [SPEC GATE 👤]
   → spec_publisher → namespace_resolver → code_developer
   → code_publisher → [CODE GATE 👤] → code_review_handoff → merge
```

Five things that make it real (lead with these):

1. **Durable, resumable state.** Each stage persists to Postgres
   (`state_snapshot`, `token_usage` as JSON). Approvals can happen minutes or
   hours later; the graph resumes from the DB snapshot. Restart-safe.

2. **Vector memory (Qdrant), dual-vector.** Specs are embedded twice — full
   content and an LLM-generated summary — so discovery retrieves related specs
   and flags duplicates by meaning, not keywords.

3. **Human-in-the-loop gates.** Two hard stops (spec, code). This is the
   product thesis: **AI-built, human-approved.** Not autonomous merge.

4. **Determinism where it matters.** Validation, the *preservation check*
   (no destructive edits), syntax checks, and **actually running the tests** are
   deterministic — the LLM's output is *checked*, not trusted.

5. **Provider-agnostic via LiteLLM.** Every model call goes through one
   abstraction. We route **each agent to a different model** via a YAML file —
   cheap/fast models for NLP stages, a strong model for code. Swap Gemini →
   Claude → a local model with **zero code change**. No vendor lock-in.

**Stack (one slide):** Django 5 + DRF, Channels/Daphne (WebSockets for live
progress), Redis (channel layer), PostgreSQL (state), Qdrant (vectors),
LangGraph (orchestration), LiteLLM (models), React + Vite + MUI (UI).

---

## 5. Differentiators (3 min) — "why not X?"

| Tool | What it does | What ADD adds |
|---|---|---|
| **Copilot / Cursor** | In-editor autocomplete | A *pipeline*: spec, review gates, tests, PRs, memory |
| **Autonomous agents** (Devin-style) | Run free, hope it works | **Governance** — humans gate every irreversible step |
| **Raw ChatGPT** | One-shot generation | Durable state, validation, vector memory, GitOps |

The elevator version: **"They generate code. We generate a governed software
delivery pipeline."**

---

## 6. Deployment & ops (3 min) — it's real infrastructure

- **GKE Autopilot**, Infrastructure-as-Code with **Terraform** (remote state in
  GCS).
- **Keyless everywhere:** GitHub Actions authenticate to GCP via **Workload
  Identity Federation** (no JSON keys); pods reach **Vertex AI** via **Workload
  Identity** (no API keys in the cluster).
- **Three GitHub Actions**, clean separation: infra (create/update), app deploy
  (build images → deploy), and a guarded destroy (cost control).
- "Only CI deploys — no one pushes from a laptop. Reproducible and auditable."

---

## 7. Q&A arsenal (anticipate the hard ones)

**"How do you stop hallucinated / broken code?"**
Three layers: deterministic validators, a preservation check that blocks
destructive edits, and we **actually run the generated tests**. If they fail,
the PR is a **draft** — never presented as done. And a human reviews at the gate.

**"How is this different from Copilot?"**
Copilot generates *inside* the editor. ADD governs the *pipeline around* the
code — spec, review, tests, PRs, and memory of prior specs. Different layer of
the problem.

**"What about cost / token spend?"**
Tracked per stage and shown live in the UI. And because of the model-routing
layer, you put a cheap model on the easy stages and a strong one only where it
pays off. You control the cost/quality trade per agent.

**"Vendor lock-in? What if we don't want Google?"**
LiteLLM abstraction. Gemini today, Claude or a self-hosted model tomorrow —
change a YAML line, no code change. We've run it on Ollama (local), Groq,
OpenRouter, and Vertex.

**"Does it scale / handle a real monorepo?"**
Today it's a POC on a demo repo. The architecture is built for it: durable
state, impact analysis to scope changes, per-namespace repo routing. Honest
about where it is: the *pipeline* is production-shaped; the *coverage* is early.

**"Data privacy — where does our code go?"**
With Vertex on GCP, calls stay in your project/region under your IAM. No keys
leave the cluster (Workload Identity). Model choice is yours.

**"What model is it using?"**
It's not one model — each stage is routed independently. For this demo: Gemini
(2.5-flash for NLP, 2.5-pro for code) via Vertex.

**"Can it modify existing code safely, not just add?"**
Yes — impact analysis picks the files, and the preservation check rejects edits
that would remove existing routes/definitions. That guard is deterministic.

---

## 8. If the demo breaks (have this ready, stay calm)

- **A stage errors live:** "Great example of why the gates exist — let me show
  you the same run I captured earlier." → have a **pre-recorded run or
  screenshots** ready. Recovering gracefully *sells the governance story*.
- **Tests fail on the live run:** lean in — "and notice it opened the PR as a
  *draft* because tests didn't pass. That's the system protecting you." It's a
  feature, not a failure.
- **Slow code stage:** talk through the architecture (§4) while it runs; the
  wait becomes your deep-dive slot.
- **Model NOT_FOUND / 403:** switch provider is a config flip — but pre-test
  tonight so this never happens live.

**Pre-flight checklist (do tonight):**
- [ ] One full dry-run on Vertex, the exact demo prompt — reaches BOTH gates.
- [ ] Spec PR + code PR actually appear in GitHub.
- [ ] Login page loads; demo creds work.
- [ ] Swagger loads; admin loads.
- [ ] Screenshots/recording of a good run saved as backup.
- [ ] Cluster left UP overnight (don't destroy before the meeting).

---

## 9. Closing (30 sec)

> "The pitch isn't 'AI writes code' — everyone has that. It's **'AI runs your
> delivery pipeline, and a human approves every decision that matters.'**
> Spec-driven, tested, gated, deployed with real IaC. That's the difference
> between a demo and a system you'd let near your codebase."

Then the ask: pilot on a real repo / next-step conversation.
