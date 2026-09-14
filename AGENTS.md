# SwarmForge Constitution

This file takes precedence over the role prompts in `.opencode/agents/`.

# Engineering Rules

## Wiring
- Harness paths come from `harness.json` (pack root, nearest upward, or `SWARM_CONFIG`/`SWARM_PACK`). Run `swarm-forge-tin/tools/harness status` for the resolved paths; never hardcode them.
- `workspace_root` is the project under work; `state_root` holds mail and team state; `artifacts_root` holds reports and caches; `hot_tests` is the shared generated area, cleaned on project switch.
- `<pack>` below means the resolved pack root (`swarm-forge-tin`, or wherever it was placed).

## Startup Tools
- On startup, procure the latest version of each required CRAP, DRY, and code-quality tool for the project language from the listed `github.com/unclebob/...` repositories or the language tool table and get each one ready to run.
- Resolve each listed repository at its latest available upstream version before installing or building it.
- Do not rely on stale cached, vendored, or preinstalled copies when a fresh GitHub install/build is possible in the current environment.
- Language tool table:
  - Go: install with `go install`; CRAP `github.com/unclebob/crap4go`, DRY `github.com/unclebob/dry4go`.
  - Clojure: install with Clojure CLI/deps.edn; CRAP `github.com/unclebob/crap4clj`, DRY `github.com/unclebob/dry4clj`.
  - Java: install with Maven (`mvn`); CRAP `github.com/unclebob/crap4java`, DRY `github.com/unclebob/dry4java`.
  - Python: install with `pip` (CRAP base `radon`, coverage `coverage`, property tests `hypothesis`, code quality `ruff`) and `npm install -g jscpd@5`; CRAP `swarm-forge-tin/tools/crap4py`, DRY `swarm-forge-tin/tools/dry4py`, code quality `swarm-forge-tin/tools/ruff4py`. Uncle Bob ships no Python repositories, so these wrappers are the language-table tools, not homegrown proxies.

## Language Defaults
- For Clojure projects, prefer Babashka where possible.
- For Clojure or Babashka projects, write Speclj specs, not `clojure.test`.
- Use the project's dependency tooling to install Speclj. Do not search `$HOME` or run `find` for binaries.
- If a Speclj spec file changed, check the spec structure before running tests.
- For Java projects, avoid using Maven to run tests; build dedicated test runners and run those instead.
- For Python projects, run tests with pytest as `python3 -m pytest`, plain and non-interactive; write property tests with hypothesis in a separate test root.
- For Python projects, run coverage, CRAP, DRY, and ruff one at a time with `coverage`, `<pack>/tools/crap4py`, `<pack>/tools/dry4py`, and `<pack>/tools/ruff4py`.

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
- The Acceptance Pipeline Specification supplies `gherkin-parser` and `ir-dry-checker`. The Babashka versions are vendored unmodified at `<pack>/tools/aps/`; call `<pack>/tools/gherkin-parser` and `<pack>/tools/ir-dry-checker`. Do not search `$HOME` or run `find` for binaries.
- Two-arg forms:
  - `<pack>/tools/gherkin-parser <feature> <artifacts>/<stem>.json`
  - `<pack>/tools/ir-dry-checker <ir> <artifacts>/<stem>.dry.json`
- The vendored APS tools are Babashka only; do not fetch or build the Go fallbacks.
- Project-specific acceptance pipeline components are the acceptance entrypoint generator, acceptance runtime, project step handlers, and convenience scripts; they live under the configured persistent test root, and generated entrypoints go to `hot_tests`.

## Project Layout
- Project source lives at the configured `source_roots` (see `harness status`); it stays test-free.
- Harness assets live under the resolved pack root (`<pack>`): `tools/`, `harness_tests/`, `project_tests/`, `hot_tests/`, `dump/`, `ruff.toml`.
- Authored harness tests live under `<pack>/harness_tests/persistent/`: `unit/`, `property/`, `features/`, `acceptance/`, `tools/`; generated tests live under `<pack>/hot_tests/`.
- Project persistent tests live at the configured `persistent_tests` roots (`unit/`, `property/`, `features/`, `acceptance/`); each root carries its own pytest configuration.
- Never create project source inside the pack; never write tests into source roots.

## Harness Commands
- Run from the workspace root; resolve paths with `<pack>/tools/harness status`. Use the wrappers only; never call `ruff`, `radon`, `jscpd`, or `coverage` directly.
- Tests: `cd <persistent-root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest`
- Property only: `cd <persistent-root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest property`
- Ruff: `<pack>/tools/ruff4py <source roots> <persistent roots>` (the wrapper already supplies `check`; never pass it)
- CRAP: `<pack>/tools/crap4py --source-root <source> --test-path <persistent tests>`
- DRY: `<pack>/tools/dry4py --min-lines 4 <source roots>`
- Acceptance: parse with `<pack>/tools/gherkin-parser` into the artifacts root, dry-check, generate into `hot_tests`, then run the generated tests.
- Gherkin: `<pack>/tools/gherkin-parser <feature> <artifacts>/<stem>.json`
- IR dry: `<pack>/tools/ir-dry-checker <ir> <artifacts>/<stem>.dry.json`
- Clean shared areas on project switch: `<pack>/tools/harness clean hot` (add `state`, `artifacts`, or `all`)
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
- Scan changed and new source files as a hint that a module may mix jobs. Split a source file when it has more than one job. Do not split a one-job module to chase a count.
- Run acceptance generation and acceptance tests sequentially.
- Avoid running whole-suite language test commands concurrently with acceptance generation.
- Run the relevant local verification command before handoff whenever the project has one. For this pack that is the persistent test suite under `<pack>/harness_tests/persistent/`.
- On legacy or untested projects, scope coverage and CRAP to the modules under work and report unmeasured functions as N/A. A failing or absent baseline does not block analysis; do not fix unrelated failing tests unless the task requires it.

## Guardrails
- Do not invent project-local CRAP, DRY, or coverage proxies. Install and run the constitution tools (`crap4clj` with cloverage, `dry4clj`, speclj, or the language table; for Python, `swarm-forge-tin/tools/crap4py` with coverage.py, `swarm-forge-tin/tools/dry4py`, and hypothesis). Do not treat a homegrown `bb crap` / `bb coverage` task as those tools.
- Do not commit unrelated local changes or generated artifacts unless required for the task.
- Never delete `harness_tests/persistent/`. Only `hot_tests/` and the configured artifacts root hold disposable artifacts.
- Before relying on an unfamiliar command, inspect local help or project documentation.

# Workflow Rules

## Workspace
- Work only in the project directory shared by all roles unless the user explicitly directs otherwise.
- Do not create git worktrees, switch branches, or base work on another branch unless the user explicitly directs it.
- Do not inspect, diff, merge, or rebase another role's uncommitted work.

## Orientation
- Read only what the task requires: the files named in the handoff message, the feature file/IR, and the reference contracts your role prompt names.
- Do not re-read your role prompt or this constitution during a task.
- Do not read `CONVERSION.md`; it is conversion history, not task guidance.
- `swarm-forge/` is a read-only upstream reference clone; do not explore it for task work.

## Announcements
- Do not add role bylines to announcements or check-in comments.

## Commit Messages
- Include your role byline in every git commit message in this form: `By <role>.`
- Example:

```text
Implement handoff validation

By coder.
```

- Commit when the user or your role prompt directs it. The user may commit on your behalf; a handoff never waits for, requires, or references a commit.
- A commit-msg hook may append `By <role>.` when it is missing. Do not skip hooks (`--no-verify`).

## Temporary Files
- Use `./tmp/` in the project directory for temporary files; do not use `/tmp`.
- Parse and dry-check into the configured artifacts root; those artifacts are reproducible and safe to delete.
- Never use `./tmp/` or the configured state root's mail directory as a communication channel; mail goes through the `mail_*` tools only.

## Failure Conditions
- If the project directory or your required inputs are missing, stop and report instead of guessing.

# Mail Protocol

All inter-role communication goes through the `mail_send`, `mail_pull`,
`mail_done`, and `mail_status` tools. Never create, read, edit, move, or delete
files under `swarm-forge-tin/.swarmforge/mail/`; the tools own queue state. Mail is durable; a
dispatch is only a lossy wake-up.

## Message Types
- `handoff` — work is ready for the next role. Requires `task`.
- `note` — one short message. Send only when the user, a role prompt, or this
  constitution explicitly directs it. Requires `message` of at most 80
  characters on one line.
- Both types accept an optional `message` (max 300 characters, one line) as a
  short pointer. Never write long handoff bodies; the tool generates the
  delivered payload.
- `task` is a short stable name. Preserve the task name you receive when
  forwarding it. The dispatcher uses the existing New Task / board card name;
  do not invent one.
- Git commits are never required to hand off work. Commit when the user or your
  role prompt directs it; a handoff never waits for, requires, or references a
  commit.

## Sending
- After completing a forward inbound task, always send the next `handoff`
  down the chain, regardless of what changed. Formatting-only, manifest-only,
  audit-only, generated metadata, and other non-functional churn still require
  a forward down the chain.
- A verification handoff from the architect is verification-only: run the
  required verification, then `mail_done`; do not forward it.
- Do not send tmux or chat notifications. `mail_send` is the notification.
- If `mail_send` reports validation errors, repair the arguments and retry.
  Never work around the tool by writing files.
- The handoff `message` names the files touched and the one fact the next role needs.
  - Good: `touched: tests/acceptance/{runtime,steps}.py, tests/property/*; 9 property tests added`
  - Bad: `done`

## Receiving
- A role is started with the wake line `MAIL_WAITING: run mail_pull`. The wake
  line never carries the task.
- Run `mail_pull`. If it prints `NO_TASK`, stop; do not invent work.
- If it prints `TASK` or `BATCH`, treat the printed `PAYLOAD` as the task and do
  the work.
- Use only the mail printed by `mail_pull`; do not go looking for other tasks.
- An in-process item is owned by the session that claimed it. `mail_pull` resumes it for that session and refuses a different session; never work on another session's item. Never pass `takeover: true` on your own; only the operator can confirm the owning session is gone.
- If a `mail_pull` or `mail_done` call was interrupted, do not assume it failed: the tool is atomic, so the transition either happened or it did not. Check `mail_status`, then run `mail_pull` again; resuming in the same session needs no takeover.
- `note` mail is a task too: act on it, then `mail_done`.
- After `mail_done`, if it prints `MAIL_WAITING`, call `mail_pull` again; if it
  prints `NO_TASK`, stop waiting for work.
- On restart, run `mail_pull` and follow its output.

## Dispatch
- Mail does not wake anyone. The operator (or the master agent) checks
  `mail_status` and resumes the recipient session with the lossy wake line
  `MAIL_WAITING: run mail_pull`.
- Do not dispatch a role that already has an in-process holder. If a role is
  dispatched twice by mistake, only the owning session may continue; the other
  must stop and report.
- A stuck session is stopped by the operator with ESC; that session then shows
  an interrupted tool call. The operator decides recovery: the same session may
  re-run `mail_pull`, or a replacement may be dispatched with `takeover: true`
  once the operator confirms the old session is stopped. Never take over from a
  live session.
- Do not dispatch another role unless the role prompt or the operator directs
  it.

# Project Rules

## Project Shape
- This project runs a four-role opencode pack: specifier, coder, refactorer, and architect.
- Project language: Python.

## Local Configuration
- Keep swarm state under the configured `state_root` (default `<pack>/.swarmforge`).

## Handoffs
- Prefer terse, explicit handoffs that report state and request role-appropriate review. Do not include verifications or sender process narrative.

## Ownership
- Do not change another role's prompt or workflow ownership without explicit user direction.

# Local Workflow Rules

## Architect Handoffs
- An architect verification handoff is handled in the dispatch that delivers it; it does not interrupt other work.
- When `mail_pull` returns mail from architect, every agent except the specifier must run unit tests and acceptance tests and fix any failures. Then run `mail_done`. Do not send forward mail for an architect verification handoff.
- Apart from verification, do not apply other role-specific work to that architect handoff.
