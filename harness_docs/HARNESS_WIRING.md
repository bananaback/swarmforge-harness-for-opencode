# Harness Wiring Design

Goal: one config-driven seam so the same `swarm-forge-tin/` pack works on the harness
itself and on any production project — no tool copies, no prompt edits per switch.

## Operator Decisions

- Hot tests and state are shared areas; switching projects is handled by an explicit
  clean (`harness clean`), no per-project namespacing required.
- `swarm-forge-tin/` may live anywhere. Discovery anchors on the `harness.json` config
  first; the old `swarm-forge-tin/tools/team.py` marker is only a fallback.
- Prompts follow the wiring: roles resolve paths from the config (or from the handoff /
  sealed pack) instead of hardcoding `swarm-forge-tin/tests/` or `src/`.

## Config

Committed at `<pack>/harness.json`, or found upward from the working directory, or
pointed at explicitly. Schema v1:

```json
{
  "version": 1,
  "workspace_root": "..",
  "state_root": ".swarmforge",
  "artifacts_root": "dump",
  "hot_tests": "hot_tests",
  "persistent_tests": [
    { "root": "harness_tests/persistent", "pythonpath": ["."], "kind": "harness" }
  ],
  "source_roots": ["tools"],
  "features": "harness_tests/persistent/features",
  "roles": ["orchestrator", "specifier", "coder", "refactorer", "architect", "mentor", "senior"]
}
```

Paths are relative to the config file's directory unless absolute or `~/...`.

| Field | Meaning |
|---|---|
| `workspace_root` | Project the roles work on; the `--root` handed to mailbox/team |
| `state_root` | Where `.swarmforge/`-style mail and team state lives |
| `artifacts_root` | Quality reports, coverage, caches (`dump/`) |
| `hot_tests` | Shared generated test area; cleaned on project switch |
| `persistent_tests` | Authored test roots, each its own pytest rootdir; `pythonpath` entries relative to the root |
| `source_roots` | Default paths for crap4py/dry4py/ruff4py when no args are given |
| `features` | Gherkin feature root for the acceptance pipeline |
| `roles` | Role list for mailbox discovery when `.opencode/agents` is absent |

## Resolution Order

Python tools: `--config` flag > `SWARM_CONFIG` env > nearest `harness.json` walking up
from CWD > `<pack>/harness.json` (pack inferred from `tools/wiring.py`) > built-in
defaults matching the old hardcoded paths.

opencode bridges (TS): `SWARM_CONFIG` / `SWARM_PACK` env > nearest `harness.json`
walking up from `context.directory` / `context.worktree` > legacy marker
`swarm-forge-tin/tools/<tool>.py` > `~/.config/swarm-forge/harness.json`.

Environment overrides for one-off switching: `SWARM_CONFIG`, `SWARM_PACK`,
`SWARM_WORKSPACE`, `SWARM_STATE_ROOT`, `SWARM_HOT`.

## Pack Test Areas

| Area | Nature | Committed |
|---|---|---|
| `harness_tests/persistent/` | harness self-tests | yes |
| `project_tests/persistent/` | src-project persistent tests, pack-side variant | yes |
| `hot_tests/` | shared generated tests and run state | no |

Project tests may instead live in the project tree; point `persistent_tests` at that root.

## Per-Tool Mapping

| Tool | Change |
|---|---|
| `tools/wiring.py` (added) | Loads `harness.json`, resolves paths, exposes `Wiring` |
| `tools/harness` (added) | `config` / `status` / `clean hot\|state\|artifacts\|all [--force]` |
| `mailbox.py`, `team.py` | State root comes from wiring/env (`--state-root` flag); default unchanged |
| `crap4py` | `--source-root`/`--test-path` unchanged; LCOV + `COVERAGE_FILE` under `artifacts_root` |
| `dry4py` | Default report under `artifacts_root/dry4py` |
| `ruff4py` | Cache under `artifacts_root/ruff-cache`; config overridable (`--config`/env), default pack `ruff.toml` |
| `gherkin-*` wrappers | Unchanged — inputs/outputs are args |
| `.opencode/lib/wiring.ts` (added) | Shared resolver used by `mail.ts`, `team.ts`, `team-autobind.ts` |
| Prompts | Replace hardcoded paths/commands with wiring or handoff-derived paths |

## Profiles

Harness development (this repo):

```json
{ "workspace_root": "..", "source_roots": ["tools"],
  "persistent_tests": [
    { "root": "harness_tests/persistent", "pythonpath": ["."], "kind": "harness" },
    { "root": "project_tests/persistent", "pythonpath": ["."], "kind": "project" }
  ] }
```

Production project (pack dropped into the project):

```json
{ "workspace_root": "..", "source_roots": ["src"],
  "persistent_tests": [{ "root": "tests", "pythonpath": ["src"], "kind": "project" }],
  "hot_tests": "~/.cache/swarm-forge/hot" }
```

Switch by editing `harness.json`, or without touching it via `SWARM_CONFIG=/path/to/other.json`.

## Isolation Rules

- Each persistent root is its own pytest rootdir with its own `pythonpath` and cache.
- Harness self-tests (`harness_tests/persistent`) never collect project tests, and vice
  versa.
- `hot_tests/` is never committed and is expected to be cleaned on project switch.
- `harness clean state` refuses while mail/team items are in process unless `--force`;
  it never touches persistent tests.

## Status

Implemented and verified by the harness's own tests (2026-09-14):

- Config + resolvers: `harness.json`, `tools/wiring.py`, `.opencode/lib/wiring.ts`.
- `tools/harness` CLI: `config`, `status`, `clean hot|state|artifacts|all [--force]`.
- Tools rewired: mailbox/team state root (`--state-root`), crap4py/dry4py/ruff4py
  artifact roots, ruff config override, TS bridges via `wiring.ts`.
- Test areas split: `harness_tests/persistent/` (self-tests), `project_tests/persistent/`
  (src project, pack-side), `hot_tests/` (shared generated).
- Acceptance pipeline restored under `harness_tests/persistent/acceptance/` and
  self-hosted: `harness_wiring.feature` (6 scenarios) generates into
  `hot_tests/acceptance/` and runs green.
- Prompts (AGENTS.md + 7 role prompts) resolve paths from the wiring or handoff.

Self-host evidence: `harness status` resolves workspace=repo root, sources=`tools`,
persistent=harness+project, hot=`hot_tests`; 25 persistent tests green; 6/6 acceptance
scenarios green; ruff clean; CRAP 0 functions above 10; DRY 0 clones.

## Next

- `team open --pack` may emit a generated `wiring.md` so workers get resolved paths
  inside the sealed pack.
- Wire `gherkin-mutator` runs to write under `hot_tests/mutation/` and report results.
- Cover the TS resolver with automated tests; today it has `node --check` plus a manual
  smoke only.
- Fill `project_tests/` when a production project is wired in.
