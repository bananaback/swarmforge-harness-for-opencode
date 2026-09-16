# Uncle Bob's SwarmForge Workflow — Concepts

## Roles

| Phase | Owns | Tools |
|---|---|---|
| Specifier | observable behavior, acceptance criteria, examples | `gherkin-parser`, `ir-dry-checker`, `question` |
| Coder | production code + focused unit tests + acceptance pipeline | `gherkin-parser`, `run_acceptance.py`, `pytest`, `ruff4py` |
| Refactorer | names, duplication, cohesion, coverage, property tests, boundaries | `crap4py`, `dry4py`, `coverage`, `run_acceptance.py`, `pytest` |
| Architect | module boundaries, dependency direction, DRY verification | `dry4py`, `ruff4py`, `pytest` |

## Specifier
- **Inputs:** operator intent.
- **Steps:**
  1. Ask questions to settle ambiguity.
  2. Write deterministic Gherkin in the APS format, separated by behavior and technology; externally visible behavior only; stable scenario name/index, the name in a comment before each feature.
  3. Make every value that might vary a parameter; prune identical example columns that add no value; move repeated setup into `Background`.
  4. `gherkin-parser` → canonical IR.
  5. `ir-dry-checker` → normalize/prune, dry report.
  6. Operator approves via `question`.
  7. Run tests only when verification is needed.
- **Outputs:** approved feature + IR + dry report.

## Coder
- **Inputs:** approved feature + IR.
- **Steps:**
  1. Implement in the project language from the constitution, starting from the latest accepted spec and architecture guidance.
  2. Write focused unit tests that would fail for a plausible wrong implementation.
  3. Write only enough production code to pass; run `pytest`.
  4. Use the APS `gherkin-parser` (prefer Babashka); build the generator, runtime, step handlers, and scripts; `run_acceptance.py` generates and runs acceptance tests.
  5. Default to regex-capture step handlers, one per repeated step shape; literal handlers only for genuinely different behavior.
  6. `ruff4py`; clear names, straightforward control flow, no avoidable duplication; leave broad cleanup to the refactorer unless it blocks the slice.
  7. Run property tests only when explicitly requested.
- **Outputs:** implementation + unit tests + step handlers; unit and acceptance green.

## Refactorer
- **Inputs:** green implementation + tests.
- **Steps:**
  1. Move behavior out of environmentally unsuitable modules into testable ones; keep unsuitable modules as small adapter shells.
  2. `crap4py` first: ≤ 10 per function; a single dispatch answering one question may exceed; nested or mixed-duty functions must split; an extract owns its inputs.
  3. `dry4py`: remove duplication.
  4. Raise coverage; add property tests where undercovered (invariants, ranges, round trips, conservation, idempotence, ordering, parse/format stability); adopt a framework or build a small one; run property tests as a separate explicit command.
  5. Split a file with more than one job before handoff.
  6. Re-run `pytest` and `run_acceptance.py`.
- **Outputs:** same behavior, lower CRAP/DRY, higher coverage.

## Architect
- **Inputs:** refactored tree.
- **Steps:**
  1. Terminal gate, one tool at a time, fixing each before the next: `dry4py` → `ruff4py` → full `pytest` suite (property separately).
  2. Review structure: UI/core separation, information hiding, dependency direction, local code quality; split modules that mix jobs or blur boundaries; minimize coupling, maximize cohesion; keep tests separate from test helpers.
  3. Keep the architecture aligned with the spec and implementation; decide design change vs simpler local fix; if the right fix is an inward call, change the automated pin.
- **Outputs:** structure verdict, only the structural fix needed; task Done.

## Verification
- A passing test is a hypothesis, not evidence; no role grades its own work.
- Acceptance pipeline: Gherkin → canonical IR → generated executable tests → runtime with step handlers.
- CRAP ≤ 10 per function; a single dispatch answering one question may exceed; nested or mixed-duty functions must split.
- DRY, coverage, and property tests, each separate; property tags stay out of normal unit/coverage runs unless the role owns property verification.
- Run one tool at a time; acceptance generation and acceptance runs stay sequential; avoid whole-suite test runs concurrent with acceptance generation.
- Prefer project-local cache and configuration paths.
- Run the local verification command before handoff; after the architect's gate, every role except the specifier reruns unit and acceptance tests.

## Design And Testability
- Maximize testable code; minimize the environmentally unsuitable boundary (GUIs, devices, environment errors, system errors, hangs).
- Only testable modules participate in unit tests, acceptance, coverage, CRAP, or test-invoking DRY.
- IO-near modules must not reimplement a domain question; call the high-level module and translate the result.
- A high-level module that exists only for tests while an adapter reimplements it is a defect.
- Dependency rule: high-level modules far from IO must not depend on low-level modules near IO.
- Keep tests close to the behavior; work in small increments; prefer the simplest design that leaves clear options for the next step; keep tests separate from test helpers.

## Startup And Tools
- Procure the latest CRAP and DRY tools from upstream; do not rely on stale cached, vendored, or preinstalled copies.
- The APS supplies `gherkin-parser` and `ir-dry-checker`; install them with the project-local helper, never by searching `$HOME` or running `find`.

## Epistemics
- Do not pin prompt prose with automated tests; test observable runtime behavior.
- No local proxies for CRAP, DRY, or coverage.
- Inspect local help or project documentation before relying on an unfamiliar command.
