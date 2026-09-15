# Testing And Acceptance

Test areas, the persistence policy, the Gherkin acceptance pipeline, spec
mutation, and the quality gates.

## Test Areas

| Area | Nature | Contents |
|---|---|---|
| `harness_tests/persistent/` | committed harness self-tests | `unit/`, `property/`, `features/`, `acceptance/`, `tools/` |
| `project_tests/persistent/` | committed src-project tests, pack-side | `unit/`, `property/`, `features/`, `acceptance/` (empty until a project is wired) |
| `hot_tests/` | generated, disposable | `acceptance/` entry points + `metadata/`; `mutation/<stem>/` |

Each persistent root is its own pytest rootdir (`pytest.ini`: `testpaths =
persistent`, `pythonpath = persistent ../tools`) with its own cache under
`dump/`. Harness tests never collect project tests, and vice versa.

## Current Inventory (2026-09-15)

- **191 persistent tests** — unit 17, property 12, tools 162 (including the M9
  branch-integration run in `tools/test_branch_integration.py`).
- **4 Gherkin features**, 28 authored scenarios, **59 generated executions**:

  | Feature | Scenarios | Executions |
  |---|---|---:|---:|
  | `harness_wiring` | 6 | 6 |
  | `task_state_layout` | 10 | 19 |
  | `deterministic_coder_payload` | 5 | 20 |
  | `deterministic_mentor_payload` | 7 | 14 |

- **16 `node:test` cases** in `persistent/tools/ts/wiring.test.ts`, driven by
  `test_ts_wiring.py` (plus a real bind-before-first-pull probe).
- **Self-hosted mutation**: `deterministic_coder_payload.feature` → 36 mutants,
  28 killed, 8 survived, 0 errors.

## Persistence Policy

Persist authored inputs; regenerate derived outputs. Any generated file is
reproducible from committed inputs plus the pinned toolchain.

| Test-related file | Hot (regenerate) | Committed | Produced by |
|---|---|---|---|
| Gherkin `.feature` specs | — | yes | authored |
| Acceptance entry points (`hot_tests/acceptance/`) | yes | no | generator from IR |
| IR JSON, dry reports, metadata | yes | no (`dump/`) | `gherkin-parser`, `ir-dry-checker` |
| Generator / runtime / step handlers | — | yes | authored harness code |
| Spec mutants and mutation results | yes | no | `gherkin-mutator` |
| Unit / property / tool tests | — | yes | authored |
| Hypothesis example DB | yes | no | hypothesis run cache |
| Coverage / CRAP / DRY / ruff reports | yes | no (`dump/`) | quality wrappers |
| Configs (`pytest.ini`, `ruff.toml`) | — | yes | authored |

Deleting `dump/` or `hot_tests/` must never delete a persistent test. Never delete
`harness_tests/persistent/` or `project_tests/persistent/`.

## Running The Tests

```bash
# harness self-tests (191)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# one kind
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/unit
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/property
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools

# opencode TS bridges (node:test suite + autobind probe; skipped without node)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools/test_ts_wiring.py

# project tests (empty until a project is wired)
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
```

Tests build temporary project roots; they touch only pytest temp dirs and never
the real project or `.swarmforge/`. Optional toolchains degrade cleanly.

## Acceptance Pipeline

Vendored, unmodified upstream: `swarm-forge-tin/tools/aps/` (Babashka tasks).
The harness calls the wrappers, never `bb` directly:

| Wrapper | APS task | Role |
|---|---|---|
| `tools/gherkin-parser <feature> <ir>` | `gherkin-parser` | Gherkin → canonical JSON IR |
| `tools/ir-dry-checker <ir> <report>` | `gherkin-ir-dry-checker` | Repeated/near-duplicate/synonym step report |
| `tools/gherkin-mutator ...` | `gherkin-mutator` | Example-value mutation (folds `--level full` → `hard`, forces `--workers 4`) |

Project-specific components live under
`harness_tests/persistent/acceptance/`:

| File | Role |
|---|---|
| `generator.py` | IR → pytest entry point + `metadata/` |
| `runtime.py` | `World` + regex step dispatch engine |
| `steps.py` | The project's `STEP_HANDLERS` |
| `run_acceptance.py` | One command: parse → dry → generate → run |
| `mutation_runner.py` | Persistent worker adapter for the mutator |
| `run_mutation.py` | One command: copy → generate → mutate → report |

### Normal Run

```bash
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py
```

For each `.feature` under the configured `features` root it:

1. parses into `<artifacts_root>/<stem>.json`;
2. dry-checks into `<artifacts_root>/<stem>.dry.json`;
3. generates `hot_tests/acceptance/test_<safe_name>_acceptance.py` and
   `hot_tests/acceptance/metadata/<feature>.json`;
4. runs `pytest hot_tests/acceptance -q -p no:cacheprovider`.

The generated file never parses the source feature — it embeds the base IR and
delegates all behavior to the runtime and step handlers.

### Runtime And Step Handlers

- `Runtime.register(pattern, handler)` appends `(compiled regex, handler)`;
  the first regex that `search`es a step text wins.
- Example values fill `<param>` placeholders; a resolved text that is fully
  quoted loses the outer quotes, and `\n`/`\t` are unescaped.
- Each scenario execution gets a fresh `World`; background steps run before
  scenario steps.
- In step files, prefer one regex handler per repeated step shape (captures for
  the varying values); write a literal handler only when the wording is
  genuinely different behavior.

### Generator And Metadata

- One test function per scenario execution: `test_<scenario>__example_<N>`.
- `SWARM_ACCEPTANCE_IR`, when set, is loaded in place of the embedded base IR —
  the seam that lets one generated file evaluate every mutant.
- `metadata/<feature>.json` records `feature_path`, `ir_path`,
  `implementation_hash` (`sha256:<hash>` of the generated files), and
  `hash_scope: generated_files`.

## Spec Mutation

Standalone (not part of the persistent suite); it checks whether example values
are actually connected to the application by mutating Gherkin example values in
the IR — not conventional source mutation.

```bash
# default level: hard; mutates every configured feature
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_mutation.py

# one feature
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_mutation.py \
  --feature swarm-forge-tin/harness_tests/persistent/features/deterministic_coder_payload.feature
```

`run_mutation.py` copies each feature into `hot_tests/mutation/<stem>/features/`
(never touching the authored feature), parses a base IR, generates entry points
once, then runs `tools/gherkin-mutator` with `--work-dir`, `--generated-dir`,
`--runner-worker`, `--level`, and `--implementation-hash`. The JSON report lands
at `<artifacts_root>/mutation/<stem>.json`; it exits `1` when any mutation
survives or errors.

`mutation_runner.py` implements the mutator's persistent worker protocol (one
newline-delimited JSON job per input line, one response per output line). It runs
the generated tests with `SWARM_ACCEPTANCE_IR` pointing at the mutated IR and
classifies pytest exit codes:

| pytest exit | Outcome |
|---|---|
| `0` | `test_success` (mutant survived) |
| `1` | `test_failure` (mutant killed) |
| other | `infrastructure_error` |

The full self-hosted run is slow (about four minutes for the 36-mutant coder
feature) because every mutant re-runs the step handlers. The persistent suite
covers the runner with a one-mutant real-mutator probe instead.

## Quality Gates

Run one tool at a time; the wrappers pass `--workers 4` where applicable.

```bash
# lint (cache under artifacts root)
swarm-forge-tin/tools/ruff4py swarm-forge-tin/tools swarm-forge-tin/harness_tests/persistent

# CRAP (radon complexity + coverage.py); 0 functions above 10
swarm-forge-tin/tools/crap4py --source-root swarm-forge-tin/tools \
  --test-path swarm-forge-tin/harness_tests/persistent

# DRY (jscpd); 0 clones
swarm-forge-tin/tools/dry4py --min-lines 4 swarm-forge-tin/tools
```

Targets: ruff clean; CRAP ≤ 10 per function (a single-question `if`/`elif` chain
may stay above 10); DRY zero clones. On legacy trees, scope coverage/CRAP to the
modules under work and report unmeasured functions as N/A.

## Caveats

- The TS bridge suite needs `node` (v22.6+ for type stripping) and is skipped
  when it is absent; it does not cover the `team.ts`/`mail.ts` registrations,
  which are exercised only through live opencode dispatch.
- The APS tools are Babashka-only; there is no Go fallback in this pack.
- Mutation is a deliberate, slow quality workflow — not a per-change gate.
