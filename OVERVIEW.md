# AI-Driven Development (ADD) — What It Is, In Plain Words

## The one-sentence version

ADD turns a plain-English request like *"add a password reset feature"* into
finished, reviewed software changes — with a human approving the work at two
checkpoints along the way.

---

## The problem it solves

Building software normally looks like this:

1. Someone writes down what they want (a "spec").
2. A developer reads it and writes the code.
3. Someone else reviews that code.
4. Tests are written to make sure it works.
5. It gets shipped.

Every one of those steps is slow, needs a skilled person, and is easy to get
wrong. ADD does the repetitive parts automatically and keeps a human in
charge of the decisions that matter.

---

## How it works — the assembly line

Think of it like an assembly line with 10 stations. You drop your request in at
one end; a finished, reviewed change comes out the other. AI does the labor;
**a person signs off twice** before anything becomes real.

**First half — agree on WHAT to build:**

1. **Look for similar work** — checks whether something like this already exists,
   so we don't build the same thing twice.
2. **Write the specification** — the AI turns your sentence into a proper,
   structured document describing exactly what should be built.
3. **Check the document** — makes sure the spec is complete and well-formed.
4. **✋ HUMAN CHECKPOINT #1** — *you* read the spec and click **Approve** or
   **Reject** (with notes). Nothing proceeds without you.

**Second half — actually BUILD it:**

5. **Find the right place** — locates which part of the existing software this
   change belongs in.
6. **Write the code and the tests** — the AI writes the actual code, writes
   tests to prove it works, **runs those tests**, and if they fail it tries to
   fix its own work automatically.
7. **Package it up** — bundles the finished code into a proposal ("pull request").
8. **✋ HUMAN CHECKPOINT #2** — *you* review the code and the test results, then
   **Approve** or **Reject**.
9. **Ship it** — once you approve, the change is merged into the real software.

---

## The key idea: the AI is never fully trusted

This is what makes ADD different from "just ask ChatGPT to write code."

- **Two human approval gates.** A person decides at both the "what" and the
  "how." The AI proposes; the human disposes.
- **Everything the AI writes gets checked by a machine** before a human ever
  sees it — the spec is validated, the code is automatically inspected, and the
  tests are *actually run*, not just written.
- **If the tests fail, it can't sneak through.** A change with failing tests is
  flagged in bright red and locked so it *can't* be shipped by accident — only
  a human deliberately overriding can push it forward.

In short: the AI does the tedious 90%, but it can't make anything real on its
own. A person is always the final word.

---

## Why this matters

- **Speed:** work that took days of back-and-forth between people can happen in
  minutes.
- **Consistency:** every change follows the same rigorous process, every time.
- **Safety:** the guardrails and the two human checkpoints mean AI mistakes get
  caught before they cause harm — you get the speed of automation without
  blindly trusting a machine.
- **A paper trail:** every step is recorded, so you can always see exactly what
  was decided and why.

---

## What to remember

> ADD is an **assembly line for software changes** where **AI does the work**
> and a **human signs off twice** — and nothing with failing tests can slip
> through.

*(This is an early proof-of-concept — it demonstrates the idea end to end, not
a finished product.)*
