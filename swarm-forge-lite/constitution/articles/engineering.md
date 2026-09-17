# Engineering

`<pack>` is the resolved pack root.

## Wiring
- Paths come from `harness.json`; resolve them with `<pack>/tools/shared/harness.py status`. Never hardcode.
- `workspace_root`: project under work. `source_roots`: test-free source. `persistent_tests`: authored tests. `hot_tests`: disposable generated area, cleaned on switch. `artifacts_root`: reports and caches. `state_root`: optional durable task state.

## Startup Tools
- Procure the latest CRAP/DRY/lint tools at their upstream GitHub versions; do not use stale, vendored, or preinstalled copies when a fresh install/build is possible.
- Go: `go install` `crap4go`, `dry4go`. Clojure: deps.edn `crap4clj`, `dry4clj`. Java: `mvn` `crap4java`, `dry4java`.
- Python: pip `radon`, `coverage`, `hypothesis`, `ruff`, plus `npm i -g jscpd@5`; CRAP `<pack>/tools/refactorer/crap4py`, DRY `<pack>/tools/shared/dry4py`, lint `<pack>/tools/shared/ruff4py`. Upstream ships no Python repo; these wrappers are the language tools.

## Language Defaults
- Python: `python3 -m pytest`, plain, non-interactive; hypothesis in a separate test root.
- Clojure: prefer Babashka; Speclj, not `clojure.test`.
- Java: no Maven test runs; build dedicated runners.
- Never search `$HOME` or run `find` for binaries; use project tooling.

## Commands
Run from the workspace root. Wrappers only: never call `ruff`, `radon`, `jscpd`, or `coverage` directly. One quality tool at a time; use `--workers 4` / `--max-workers 4`.
- Tests: `cd <persistent-root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest`; property only: `... pytest property`.
- Ruff: `<pack>/tools/shared/ruff4py <source roots> <persistent roots>` (never pass `check`).
- CRAP: `<pack>/tools/refactorer/crap4py --source-root <source> --test-path <persistent tests>`. It runs coverage.py; there is no separate coverage command.
- DRY: `<pack>/tools/shared/dry4py --min-lines 4 <source roots>`.
- Gherkin: `<pack>/tools/shared/gherkin-parser <feature> <artifacts>/<stem>.json`.
- IR dry: `<pack>/tools/specifier/ir-dry-checker <ir> <artifacts>/<stem>.dry.json`.
- Acceptance: parse into the artifacts root, dry-check, generate into `hot_tests`, run the generated tests; runner `<persistent>/acceptance/run_acceptance.py`.
- Clean on project switch: `<pack>/tools/shared/harness.py clean hot` (`state`, `artifacts`, `all`).

## Layout
- Source lives under `source_roots` and stays test-free. Authored tests: `persistent_tests/{unit,property,features,acceptance}`; harness tool tests: `<pack>/harness_tests/persistent/tools`. Generated tests: `<pack>/hot_tests`, disposable, never committed.
- Never create project source in the pack; never write tests into source roots.
- `artifacts_root` holds only reproducible artifacts. Deleting it or `hot_tests` must never delete a persistent test; never delete `<pack>/harness_tests/persistent/`.

## Design
- Small increments; the simplest design for the current behavior; tests close to the behavior.
- Separate testable modules from unsuitable ones (GUI, devices, env/system errors, hangs). Maximize testable code, minimize the boundary.
- IO-near modules call the domain module; never reimplement its answer.
- Only testable modules participate in unit tests, acceptance, CRAP, DRY, or property tests.
- Property tests stay separate; no property tags in unit/CRAP runs unless the role owns them.

## Acceptance
- APS: `gherkin-parser` + `ir-dry-checker`, Babashka, vendored unmodified at `<pack>/tools/shared/aps/`; do not fetch the Go fallbacks.
- Mutation (language or Gherkin) is out of scope. Meaningfulness = acceptance suite + property tests + architect review.
- Project acceptance components (generator, runtime, step handlers, scripts) live under the persistent test root; generated entrypoints go to `hot_tests`.

## Verification
- Run tools one at a time; never CRAP/DRY/ruff concurrently.
- Acceptance generation and runs sequential; no whole-suite test run concurrent with acceptance generation.
- Prefer project-local cache/config paths; avoid writes outside the project.
- Architect gate: DRY then ruff then the full persistent suite, plus the acceptance runner.
- Run the relevant local verification command before handing off.
- Split a source file with more than one job; do not split a one-job module to chase a count.
- Scope CRAP to the modules under work; unmeasured functions are N/A; an absent or failing baseline does not block.

## Guardrails
- No project-local CRAP/DRY/coverage proxies; use the wrappers.
- Do not commit unrelated changes or generated artifacts.
- Inspect local help or docs before an unfamiliar command.
