# SwarmForge Lite Constitution

This file takes precedence over the role prompts in `.opencode/agents/`.

# Engineering Rules

## Wiring
- Harness paths come from `harness.json` (pack root, nearest upward, or `SWARM_CONFIG`/`SWARM_PACK`). Run `swarm-forge-lite/tools/shared/harness.py status` for the resolved paths; never hardcode them.
- `workspace_root` is the project under work; `state_root` holds optional durable task state; `artifacts_root` holds reports and caches; `hot_tests` is the shared generated area, cleaned on project switch.
- `<pack>` below means the resolved pack root (`swarm-forge-lite`, or wherever it was placed).

## Startup Tools
- On startup, procure the latest version of each required CRAP, DRY, and code-quality tool for the project language from the listed `github.com/unclebob/...` repositories or the language tool table and get each one ready to run.
- Resolve each listed repository at its latest available upstream version before installing or building it.
- Do not rely on stale cached, vendored, or preinstalled copies when a fresh GitHub install/build is possible in the current environment.
- Language tool table:
  - Go: install with `go install`; CRAP `github.com/unclebob/crap4go`, DRY `github.com/unclebob/dry4go`.
  - Clojure: install with Clojure CLI/deps.edn; CRAP `github.com/unclebob/crap4clj`, DRY `github.com/unclebob/dry4clj`.
  - Java: install with Maven (`mvn`); CRAP `github.com/unclebob/crap4java`, DRY `github.com/unclebob/dry4java`.
  - Python: install with `pip` (CRAP base `radon`, coverage `coverage`, property tests `hypothesis`, code quality `ruff`) and `npm install -g jscpd@5`; CRAP `swarm-forge-lite/tools/refactorer/crap4py`, DRY `swarm-forge-lite/tools/shared/dry4py`, code quality `swarm-forge-lite/tools/shared/ruff4py`. Uncle Bob ships no Python repositories, so these wrappers are the language-table tools, not homegrown proxies.

## Language Defaults
- For Clojure projects, prefer Babashka where possible.
- For Clojure or Babashka projects, write Speclj specs, not `clojure.test`.
- Use the project's dependency tooling to install Speclj. Do not search `$HOME` or run `find` for binaries.
- If a Speclj spec file changed, check the spec structure before running tests.
- For Java projects, avoid using Maven to run tests; build dedicated test runners and run those instead.
- For Python projects, run tests with pytest as `python3 -m pytest`, plain and non-interactive; write property tests with hypothesis in a separate test root.
- For Python projects, run coverage, CRAP, DRY, and ruff one at a time with `coverage`, `<pack>/tools/refactorer/crap4py`, `<pack>/tools/shared/dry4py`, and `<pack>/tools/shared/ruff4py`.

## Design And Testability
- Work in small, reviewable increments.
- Prefer the simplest design that supports the current behavior and leaves clear options for the next step.
- Keep tests close to the behavior being changed.
- Separate testable modules from environmentally unsuitable modules that open GUIs, depend on external devices, throw environment errors, emit system errors, or hang under automated tests. Maximize testable code and minimize the unsuitable boundary.
- IO-near modules must not reimplement a domain question. If a high-level module already answers it, call that module and translate the result. Walking the same facts again is a defect even when the dependency arrow already points inward.
- Only testable modules should participate in tools that run tests, including unit tests, acceptance tests, coverage, CRAP analysis, DRY analysis that invokes tests, and property tests.
- Keep property tests separate from normal verification. Do not include property-test tags in normal unit coverage, CRAP, or coverage commands unless the role owns property-test verification or the user explicitly asks for property tests.

## Acceptance Pipeline
- Use github.com/unclebob/Acceptance-Pipeline-Specification for Gherkin acceptance tests.
- The APS supplies `gherkin-parser` and `ir-dry-checker`. The Babashka versions are vendored unmodified at `<pack>/tools/shared/aps/`; call `<pack>/tools/shared/gherkin-parser` and `<pack>/tools/specifier/ir-dry-checker`. Do not search `$HOME` or run `find` for binaries.
- Two-arg forms:
  - `<pack>/tools/shared/gherkin-parser <feature> <artifacts>/<stem>.json`
  - `<pack>/tools/specifier/ir-dry-checker <ir> <artifacts>/<stem>.dry.json`
- The vendored APS tools are Babashka only; do not fetch or build the Go fallbacks.
- Mutation is out of scope for this pack (operator decision): neither language-source mutation nor spec/Gherkin mutation runs. Test meaningfulness is carried by the acceptance suite, property tests, and the architect's review.
- Project-specific acceptance pipeline components are the acceptance entrypoint generator, acceptance runtime, project step handlers, and convenience scripts; they live under the configured persistent test root, and generated entrypoints go to `hot_tests`.

## Project Layout
- Project source lives at the configured `source_roots` (see `harness.py status`); it stays test-free.
- Harness assets live under the resolved pack root (`<pack>`): `tools/`, `harness_tests/`, `project_tests/`, `hot_tests/`, `dump/`, `ruff.toml`.
- Authored harness tests live under `<pack>/harness_tests/persistent/`: `unit/`, `property/`, `features/`, `acceptance/`, `tools/`; generated tests live under `<pack>/hot_tests/`.
- Project persistent tests live at the configured `persistent_tests` roots (`unit/`, `property/`, `features/`, `acceptance/`); each root carries its own pytest configuration.
- Never create project source inside the pack; never write tests into source roots.

## Harness Commands
- Run from the workspace root; resolve paths with `<pack>/tools/shared/harness.py status`. Use the wrappers only; never call `ruff`, `radon`, `jscpd`, or `coverage` directly.
- Tests: `cd <persistent-root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest`
- Property only: `cd <persistent-root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest property`
- Ruff: `<pack>/tools/shared/ruff4py <source roots> <persistent roots>` (the wrapper already supplies `check`; never pass it)
- CRAP: `<pack>/tools/refactorer/crap4py --source-root <source> --test-path <persistent tests>`
- DRY: `<pack>/tools/shared/dry4py --min-lines 4 <source roots>`
- Acceptance: parse with `<pack>/tools/shared/gherkin-parser` into the artifacts root, dry-check, generate into `hot_tests`, then run the generated tests; the project runner is `<persistent>/acceptance/run_acceptance.py`.
- Gherkin: `<pack>/tools/shared/gherkin-parser <feature> <artifacts>/<stem>.json`
- IR dry: `<pack>/tools/specifier/ir-dry-checker <ir> <artifacts>/<stem>.dry.json`
- Mutation: not run in this pack (operator decision).
- Clean shared areas on project switch: `<pack>/tools/shared/harness.py clean hot` (add `state`, `artifacts`, or `all`)
- Run quality tools one at a time; use `--workers 4` / `--max-workers 4` where supported.

## Test Layout
- Authored tests live under the configured persistent roots and persist. Never write tests into the project source tree.
  - `unit/`: TDD unit tests.
  - `property/`: property tests.
  - `features/`: authored Gherkin specs.
  - `acceptance/`: step handlers and runtime for those specs.
  - `tools/`: harness tool tests (harness area only).
- Generated tests live under `<pack>/hot_tests/`; they are disposable and never committed.
- Project persistent tests live at the configured `persistent_tests` roots, each with its own `pytest.ini`/`conftest.py` and `pythonpath`.
- Run tests as `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest` from the persistent root, plain and non-interactive.
- The artifacts root holds only reproducible artifacts (parse IR, dry reports, coverage data, pytest and hypothesis caches, ruff cache). Deleting it or `hot_tests/` must never delete a persistent test; never delete `<pack>/harness_tests/persistent/`.

## Verification
- Before running language, build, or test commands, prefer project-local cache/configuration paths inside the project directory. Avoid default cache locations that write outside the project and may trigger sandbox or permission restrictions.
- Run constitution tools one at a time. Do not run CRAP, DRY, coverage, ruff, or structure-check concurrently.
- Tools that take a worker limit must use `--max-workers 4` or `--workers 4`.
- Mutation (language-source or Gherkin) is out of scope for this pack (operator decision). The architect's gate is DRY, ruff, and the full persistent suite plus the structure review.
- Scan changed and new source files as a hint that a module may mix jobs. Split a source file when it has more than one job. Do not split a one-job module to chase a count.
- Run acceptance generation and acceptance tests sequentially.
- Avoid running whole-suite language test commands concurrently with acceptance generation.
- Run the relevant local verification command before handing off whenever the project has one. For this pack that is the persistent test suite under `<pack>/harness_tests/persistent/`.
- On legacy or untested projects, scope coverage and CRAP to the modules under work and report unmeasured functions as N/A. A failing or absent baseline does not block analysis; do not fix unrelated failing tests unless the task requires it.

## Guardrails
- Do not invent project-local CRAP, DRY, or coverage proxies. Install and run the constitution tools (`crap4clj` with cloverage, `dry4clj`, speclj, or the language table; for Python, `swarm-forge-lite/tools/refactorer/crap4py` with coverage.py, `swarm-forge-lite/tools/shared/dry4py`, and hypothesis). Do not treat a homegrown `bb crap` / `bb coverage` task as those tools.
- Do not commit unrelated local changes or generated artifacts unless required for the task.
- Never delete `harness_tests/persistent/`. Only `hot_tests/` and the configured artifacts root hold disposable artifacts.
- Before relying on an unfamiliar command, inspect local help or project documentation.

# Workflow Rules

## Workspace
- Work only in the project directory shared by all roles unless the user explicitly directs otherwise.
- Do not create git worktrees, switch branches, or base work on another branch unless the user explicitly directs it.
- Do not inspect, diff, merge, or rebase another role's uncommitted work.

## Orientation
- Read only what the task requires: the inbound message, the feature file/IR, and the reference contracts your role prompt names.
- Do not re-read your role prompt or this constitution during a task.
- Do not read `CONVERSION.md`; it is conversion history, not task guidance.
- `uncle_bob_swarmforge_reference/` is a read-only upstream reference clone; do not explore it for task work.

## Commit Messages
- Follow the Angular commit message convention: `<type>(<scope>): <summary>`.
- `type` is one of `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `test`. `scope` is optional and names the affected area.
- Write the summary in the imperative present tense, lowercase, without a trailing period.
- Add a body when the change needs context: what changed and why, wrapped at 72 columns. Mark breaking changes with a `BREAKING CHANGE:` footer.
- Example:

```text
feat(coder): add a reasoning scaffold to the role message

The next role now gets a decision, the reason, and the next change to try.
```

- Commit when the user or your role prompt directs it. The user may commit on your behalf; handing off never waits for, requires, or references a commit.

## Temporary Files
- Use `./tmp/` in the project directory for temporary files; do not use `/tmp`.
- Parse and dry-check into the configured artifacts root; those artifacts are reproducible and safe to delete.
- Messages between roles are live (the `task` tool); do not use `./tmp/` as a communication channel.

## Failure Conditions
- If the project directory or your required inputs are missing, stop and report instead of guessing.

# Communication

The orchestrator is the only dispatcher. It calls one role at a time with the
opencode `task` tool and reads that role's final message. A role runs as a
subagent (`subagent_depth` is 1) and never calls `task` itself.

## Calling
- Only the orchestrator calls the `task` tool: `subagent_type` is the role,
  `prompt` is the message from `<pack>/protocol/dispatch.md`.
- Omit `task_id` to start a fresh session; pass the `task_id` returned by an
  earlier call to resume that session (the cache hit) when you talk to the same
  role again.
- The callee's final message is returned as the `task` tool result.

## Answering
- End your turn with the message from your role template under `<pack>/protocol/`:
  the specifier uses `specifier.md`, the coder `coder.md`, the refactorer
  `refactorer.md`, the architect `architect.md`.
- Never call the `task` tool from a role: nested subagents are refused by the
  depth limit, so an attempted dispatch fails. The role answers; the orchestrator
  makes the next call.
- The templates are plain text; edit them there to change a format.

## Chain
- The chain is `specifier -> coder -> refactorer -> architect`. The orchestrator
  forwards always, even when nothing changed; it preserves the inbound task name.
- A role's `NEXT` names the role the orchestrator dispatches next, not a role the
  role itself calls.
- The architect's terminal message addresses the whole pack; the orchestrator
  relays it and the recipients verify and stop, they do not forward it.
- A message never waits for, requires, or references a commit. Leave the tree for
  the next role.

## Evidence
- A message carries the oracle command and its exit code. A green claim with no
  oracle result is not evidence.
- No role certifies its own work.

## Gates
- The specifier gates on operator approval with the `question` tool before any
  message.
- Ambiguity, contradiction, or a spec/test conflict is escalated with `question`;
  never guessed and never carried in chat.

## Dispatch
- The orchestrator spawns one role at a time with the `task` tool and reads the
  message it returns; it does no role work.
- Never brief a role to dispatch the next role. Ask it to answer with `NEXT`, and
  let the orchestrator make the next call.
- Chunks with pairwise-disjoint file allowlists may run at once; a chunk never
  edits outside its allowlist.

# Project Rules

## Project Shape
- This project runs a four-role pack plus an orchestrator: specifier, coder, refactorer, and architect.
- Project language: Python.

## Local Configuration
- `state_root` (default `<pack>/.swarmforge`) is reserved for optional durable task state; communication itself is live.

## Ownership
- Do not change another role's prompt or workflow ownership without explicit user direction.

# Local Workflow Rules

## Spec Approval
- Before implementation begins, the specifier gates its handoff on operator
  approval using the `question` tool (`Approve` / `Request changes` / `Stop`). The
  specifier never calls the coder; after `Approve` it answers with `NEXT: coder`
  and the orchestrator dispatches the coder.

## Architect Verification
- The architect's terminal message is verification-only. The orchestrator relays
  it; every non-specifier role re-runs unit and acceptance tests, fixes failures,
  then stops. Do not forward it.
