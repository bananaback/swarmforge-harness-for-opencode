# Uncle Bob's TDD Workflow — Concepts

Distilled from `github.com/unclebob/swarm-forge`, branches **`main`** (shared
engineering law / handoff protocol) and **`four-pack`** (the `specifier → coder →
refactorer → architect` workflow), as of commit `f4f5fbc` (main).

Scope: the *concepts* only. Tooling, scripts, tmux/worktree mechanics, dashboards,
and file layouts are intentionally abstracted away. Where a concept comes from the
shared constitution it is cited as `engineering.prompt` / `workflow.prompt` /
`handoffs.prompt`; from the pack, as `specifier.prompt` etc.; conceptual
proposals come from the handoff protocol and platoon brainstorm.

---

## 1. The central idea: TDD is a division of disciplines, not a single loop

The four-pack separates four engineering activities that are normally blurred
together in one developer's head:

| Phase | Discipline | Owns | Does not own |
|---|---|---|---|
| Specifier | Specification | Observable behavior, acceptance criteria, examples | Implementation detail |
| Coder | Implementation (TDD) | Production code + focused unit tests + acceptance pipeline | Cleanup, mutation, CRAP, DRY |
| Refactorer | Behavior-preserving cleanup | Names, cohesion, duplication, coverage, property tests, boundaries | New behavior, mutation tests |
| Architect | Architecture / final verification | Module boundaries, dependency direction, mutation, DRY verification | Redoing cleanup, changing behavior |

The workflow is `New Task → specifier → approval → coder → refactorer →
architect → Done`. Each phase is a *different question* asked of the same code:
what should it do, does it do it, is it well-built, is it well-structured. TDD is
not "write a test then code"; it is a pipeline in which each role's output is the
next role's input, and no role grades its own work.

**The pack-selection concept.** A four-pack is chosen when a component needs
Gherkin acceptance tests — typically components that contain business rules. A
two-pack (no acceptance tests) is for simple utilities; a six-pack adds dedicated
hardening and QA when there is a real user interface. The workflow's weight is
matched to how much specification discipline the component deserves.

## 2. Specification first — behavior is fixed, implementation is free

- The specifier turns operator intent into **deterministic, testable Gherkin**
  and examples. The specifier's anti-goal is to prescribe implementation:
  specifications fix *externally visible behavior*, and nothing else.
- Specs are organized by behavior and technology; each scenario carries a stable
  name/index so it can be referenced and mutated later.
- Specs are **mutation-tested**, which forces parameters to be real: any field
  that might vary must be a Gherkin parameter, and example-table columns that
  never vary (and add nothing to mutation) are pruned. A specification is
  therefore written not just to describe behavior but to *survive mutation* —
  every value in it is presumed to be load-bearing.
- The specifier does not run Gherkin mutation itself. Writing the spec and
  testing the spec are separate responsibilities.

## 3. The TDD loop at implementation

The coder's law is explicit:

> Use TDD to specify behavior before implementation. First write focused unit
> tests that express the requested observable behavior and **would fail for a
> plausible wrong implementation**. Then write only enough production code to
> pass those tests. (`coder.prompt`)

Concepts embedded in that one rule:

- **Test before production code.** The test is the specification of the slice.
- **A test is only legitimate if a plausible wrong implementation would fail it.**
  This is the falsifiability test for tests themselves. A test that cannot fail
  proves nothing.
- **Write only enough code to pass.** No speculative behavior; the test bounds
  the work.
- **Generated acceptance tests are not a substitute for unit tests.** Acceptance
  proves the behavior end-to-end; unit tests pin the slice. They are different
  tools with different jobs and are kept separate.
- **Property tests are opt-in**, run only when requested or when the slice
  specifically calls for them, and never mixed into normal unit/coverage/mutation
  runs.

## 4. What makes a test trustworthy: the verification stack

Uncle Bob's harness does not trust a green test. It layers independent checks
that a test is actually connected to behavior:

1. **Acceptance pipeline.** Gherkin → canonical IR → generated executable tests →
   runtime with step handlers. The generated entry point must not re-parse the
   feature; it embeds/loads the IR and delegates behavior to the runtime and
   project step handlers. Step handlers default to regex-based parameter
   extraction, with one handler per repeated step shape.
2. **Gherkin acceptance mutation.** The spec's example values are mutated, and a
   surviving mutant means an example value never reached the implementation.
   Consequently a green acceptance suite that survives mutation is meaningful;
   one whose mutants survive is hollow.
3. **Language source mutation.** Uncovered code and surviving mutants are found
   and killed. Mutation is **differential against a durable manifest** — never
   `--mutate-all`, never hand-edited manifests. The manifest is the record of
   what has already been proven.
4. **CRAP** (complexity adjusted for coverage) ≤ 10 per function, with a narrow
   exception for a single dispatch/`cond`/`case` that answers one question.
5. **DRY**, coverage, and **property tests**, each separate.

The deep concept: *a passing test is a hypothesis, not evidence.* Evidence is
produced by trying to break the test (mutation) and by measuring whether the code
is simple enough to be fully exercised (CRAP/coverage).

## 5. Design and testability

- **Maximize testable code; minimize the environmentally unsuitable boundary.**
  Whatever opens GUIs, talks to devices, throws environment errors, emits system
  errors, or hangs under automation is pushed behind a small adapter shell and
  excluded from every tool that runs tests.
- **Only testable modules participate** in unit tests, acceptance tests, coverage,
  mutation, CRAP, or test-invoking DRY.
- **IO-near modules must not reimplement a domain question.** If a high-level
  module already answers it, the adapter calls that module and translates the
  result. Re-deriving the same facts in the adapter is a defect *even when the
  dependency arrow already points inward*.
- **A high-level module that exists only for tests while an adapter reimplements
  it is a defect.** Either wire the adapter to the policy or delete the unused
  policy.
- **Keep tests close to the behavior being changed.**
- **Work in small, reviewable increments.**
- **Prefer the simplest design that supports current behavior and leaves clear
  options for the next step.**
- **Dependency Rule:** high-level modules far from IO must not depend on
  low-level modules near IO; low-level modules depend on high-level abstractions
  or call inward. This is stated for architecture and even for components inside
  a larger system (platoon brainstorm): interfaces are owned by the *higher-level*
  component and implemented by the lower-level one, so the lower level acts as a
  plugin even when runtime calls flow the other way.

## 6. Refactoring is a separate, behavior-preserving phase

- The refactorer improves names, duplication, cohesion, boundaries, and
  testability **without changing observable behavior**. Its anti-goal is to
  introduce behavior.
- It runs CRAP and DRY, raises coverage where reasonable, and owns property-test
  support (find a suitable framework, or build a small one).
- It **does not run mutation tests** and does not run Gherkin mutation. Mutation
  is deliberately reserved for the architect, so the role that cleans up cannot
  also certify that the tests are meaningful.
- Structural cleanup is deferred to this phase: the coder leaves broad cleanup
  alone unless it blocks the slice.

## 7. Architecture is the final, independent gate

The architect asks whether the code is well-*structured*, not whether it works
(that is already proven) and not whether it is tidy (that was the refactorer):

- **UI/Core separation.** For every observable the UI presents from application
  state, find the domain function that already knows it; the UI asks that
  function rather than reimplementing the rule.
- **Information hiding / encapsulation.** Expose only necessary concepts; hide
  representation and IO; preserve invariants; do not leak framework or
  persistence structures across boundaries.
- **Dependency direction** (see §5).
- **Local code quality** as it affects architectural clarity: names, control
  flow, duplication, error handling, edge cases.
- It runs the terminal verification sequence: language mutation, then DRY, then
  soft Gherkin mutation, fixing each before the next. Its handbacks are
  merge-only and never re-forwarded.

The architect's verdict is the last word before Done. Automated architecture
checks describe *intended* structure, not accidents: if the right fix is an
inward call, the pin changes.

## 8. Independent verification and the ownership of quality tools

The most important structural concept: **no role certifies its own work.**

- The coder may not run mutation, CRAP, DRY, or Gherkin mutation.
- The refactorer may not run mutation or Gherkin mutation.
- The architect runs mutation, DRY, and soft Gherkin mutation.
- The specifier may not run Gherkin mutation.

TDD's "green" is the coder's local signal; the *trustworthy* green is produced by
a different role running different tools. Verification is not a formality — on an
architect handback, **every role except the specifier must run unit and
acceptance tests and fix any failures** before completing the item. An architect
handback is handled when it is delivered, and it does not interrupt work already
in progress.

## 9. Workflow and handoff concepts (abstracted)

- **Committed work is the unit of exchange.** A handoff transfers a commit, not a
  live shared state. The receiver merges the commit and processes from there.
  Work is durable because it is committed; the wake-up is lossy and content-free.
- **A handoff is structured, terse, and machine-validated.** Only two message
  types: `git_handoff` (committed work for another role) and `note` (one short
  line, sent only when explicitly authorized). Drafts carry only route fields;
  the delivery machinery supplies identity, timestamps, and evidence. Agents must
  repair validation errors and retry, never bypass the validator.
- **The task name is stable and preserved** as work moves between roles; the
  operator's board-card name is the canonical name, never invented.
- **Forward, always.** After completing a forward task, a role always hands off
  to the next role in the chain — even if nothing changed (formatting-only,
  manifest-only, audit-only churn still forwards). The chain is the heartbeat.
- **Terminal broadcast.** The last role's handoff addressed to *every other*
  role is what marks the card Done; a partial addressee list is not terminal.
  Recipients merge only and stop.
- **Reverse handbacks exist so structure can flow backward.** A role can be
  configured to queue merge-only copies to earlier roles after downstream work
  (the refactorer sends back one; the architect broadcasts back to all). This is
  how the architect's improved structure reaches the roles whose code it
  restructured.
- **Structure improves as work moves down the pack.** This is a merge-direction
  rule with philosophical weight:
  - On a **forward** handoff, *your current tree is the structure*; replay the
    inbound work onto your shape. Do not adopt the inbound layout to save merge
    work.
  - On a **reverse/back** handback, *the inbound tree is the structure*; replay
    your current task onto that shape. Do not keep your earlier layout to save
    local work.
  In both cases the *later, better structure wins*, and saving merge effort is
  explicitly not a reason to preserve the older shape.
- **Conflicts are expected and owned.** Parallel work on one tree will conflict;
  the receiver resolves every conflict and commits. Conflict resolution is
  engineering work, not an error.
- **The operator is in the loop at gates, not in the pane.** Agents do not ask
  questions in chat. Ambiguity, contradiction, or a test/specification conflict
  is escalated through an explicit clarify request; the specifier's handoff is
  held for operator approval before implementation begins. Agents do not request
  approval conversationally.
- **One item at a time per role** (with `batch` as an explicit mode for roles
  that should consume a compatible group together). Isolated per-role workspaces
  physically prevent roles from colliding.
- **Audit is structural.** The sender's handoff passes a mandatory re-audit gate
  before it is queued: the sender must re-read the full inbound payload and
  sources, trace every requirement and constraint to work and evidence, examine
  boundaries and failure cases, and fix findings. **Passing checks alone do not
  establish completeness.** The gate is cumulative across the task and survives
  lane changes, approvals, and retries.

## 10. Epistemics and meta-concepts

- **Do not pin prompt prose with automated tests.** Prompt/constitution wording
  is not production behavior; test observable runtime behavior instead. (This
  applies to the constitution articles, role prompts, Tool Startup, and generated
  instruction files.) A harness must not mistake its own instructions for its
  behavior.
- **Procure tools freshly from upstream.** On startup, get the latest CRAP,
  mutation, and DRY tools for the language from their upstream repositories and
  make them ready to run; do not rely on stale cached, vendored, or preinstalled
  copies. Measurement tools are part of the evidence chain and must be current.
- **Language defaults serve fast, controlled testing.** Prefer Babashka/Clojure
  where possible; use speclj specs and run a structure check after spec changes;
  for Java, avoid Maven for running tests and build dedicated test runners. The
  point is tight, predictable, cheap test execution.
- **No proxies.** Do not invent project-local CRAP/DRY/mutation/coverage
  substitutes and do not treat a homegrown task as the real tool. Evidence must
  come from the named instruments.
- **Verification is sequential.** Run constitution tools one at a time — never
  CRAP, DRY, coverage, language mutation, Gherkin mutation, or structure checks
  concurrently. Keep acceptance generation and acceptance test runs sequential.
- **Keep the harness's own state and the product's source separate.** Generated
  coordination state is transport, not product source; agents must not edit it as
  a substitute for the proper commands.

## 11. One-paragraph summary

TDD in SwarmForge is a pipeline of four disciplines over committed artifacts:
a specifier writes mutation-ready Gherkin that fixes observable behavior and
forbids implementation detail; a coder writes the failing unit test first, the
smallest passing implementation, and an acceptance pipeline in which generated
tests delegate to real step handlers; a refactorer reshapes the code without
changing behavior while raising coverage and property-test support; and an
architect verifies structure, dependency direction, information hiding, and the
meaningfulness of the tests by mutation and DRY. No role certifies its own work;
every tool that can disprove a test is owned by a different role than the one
that wrote it. Structure improves as work flows forward (and back), the operator
gates specifications and resolves ambiguity, and evidence — not green alone — is
what closes a task.
