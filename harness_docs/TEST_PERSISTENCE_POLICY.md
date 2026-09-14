# Test Persistence Policy

Which test-related files are **hot artifacts** (generated, reproducible, never committed)
and which are **authored inputs** (live in the repo).

**Principle:** persist authored inputs; regenerate derived outputs. Any generated file
can be reproduced from committed inputs plus the pinned toolchain.

## Test Types

| Test type | Hot (generated → reproduce) | Persist in repo | Produced by / regenerated with |
|---|---|---|---|
| Gherkin `.feature` specs | — | yes — source of truth | authored |
| Acceptance entrypoints (`hot_tests/acceptance/`) | yes | no | generator from IR |
| IR JSON, dry reports, metadata, dry-check output | yes | no (`dump/`) | `gherkin-parser`, `ir-dry-checker` |
| Generator / runtime / step handlers | — | yes — they *are* harness code | authored |
| Spec mutation (mutants, mutation results) | yes | no | `gherkin-mutator` reruns |
| Unit tests | — | yes | authored |
| Property tests | — | yes | authored |
| Hypothesis example DB | yes | no | hypothesis run cache |
| Harness tool tests | — | yes | authored |
| Coverage / CRAP / DRY / ruff reports | yes | no (`dump/`) | `crap4py`, `dry4py`, `ruff4py` |
| Configs (`pytest.ini`, `ruff.toml`, thresholds) | — | yes | authored |

## Current State

The pack is self-hosting as of 2026-09-14:

- `harness_tests/persistent/` holds 25 authored tests (unit, property, tools) and one
  Gherkin feature (`harness_wiring.feature`, 6 scenarios).
- The acceptance pipeline (`runtime.py`, `steps.py`, `generator.py`, `run_acceptance.py`)
  lives under `harness_tests/persistent/acceptance/` and generates entrypoints into
  `hot_tests/acceptance/`, including `metadata/` with the implementation hash.
- `project_tests/persistent/` is the pack-side home for src-project tests; empty until a
  project is wired in.
- `dump/` currently holds the self-hosted run artifacts (parse IR, dry report, coverage,
  DRY report, caches) and is disposable.

Verification: 25 tests green, 6/6 acceptance scenarios green, ruff clean, CRAP 0
functions above 10, DRY 0 clones.

## Caveats

- A generated file only earns a commit when CI cannot run its generator (for example,
  no Babashka/APS toolchain). Then pin tool versions and verify the implementation hash
  (APS metadata already emits a `sha256` hash).
- `dump/` is disposable by design; deleting it must never delete an authored test.
- Hot artifacts should stay out of git (see `.gitignore`) and be rebuildable with one
  command per tool.
