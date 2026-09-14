# Project Structure Map

Scouted map of `/home/vttin1/harness_research`, updated 2026-09-14 after the wiring
implementation and the self-hosted test run.

**Shape:** self-hosting harness repo. The pack points at this repository
(`workspace_root = ".."`, `source_roots = ["tools"]`), its own tests live under
`harness_tests/`, and the acceptance pipeline regenerates entrypoints into the shared
`hot_tests/`. Working tree is currently uncommitted.

## Top-Level Areas

| Area | Role |
|---|---|
| `swarm-forge-tin/` | The harness pack: `harness.json` wiring, `tools/` CLIs, `harness_tests/`, `project_tests/`, `hot_tests/`, `dump/` |
| `.opencode/` | Agent pack: 7 role agents, `lib/` resolvers, autobind plugin, `mail`/`team` tool bridges |
| `harness_docs/` | All project documentation (index in `harness_docs/README.md`) |
| `AGENTS.md` | Constitution / opencode instruction file — stays at root by convention |
| `opencode.json` | Default + small model `opencode-go/mimo-v2.5`, model tiers, `AGENTS.md` instructions |
| `.gitignore` | Ignores bytecode, venvs, coverage, tool caches, `node_modules`, `.swarmforge/`, `dump/*`, `hot_tests/` |

## Full Tree

```
harness_research/
├── AGENTS.md, opencode.json, .gitignore
├── harness_docs/
│   ├── README.md                       doc index + status snapshot
│   ├── CONVERSION.md                   conversion history (do not read per AGENTS.md)
│   ├── HARNESS_WIRING.md               wiring design, status, next steps
│   ├── PROJECT_STRUCTURE.md            this map
│   ├── TEAM_JOURNAL_EXAMPLE.md         worker journal sample
│   ├── TEAM_TOOL_DESIGN.md             team tool design
│   ├── TEST_PERSISTENCE_POLICY.md      hot vs persistent test policy
│   ├── WORKFLOW_ROUTING.md             model tiers + role routing
│   └── prompting-guide.md              reference notes (not part of the pack)
├── .opencode/
│   ├── agents/{orchestrator,specifier,coder,refactorer,architect,mentor,senior}.md
│   ├── lib/team-autobind.ts            seat auto-bind logic
│   ├── lib/wiring.ts                   TS wiring resolver (mirrors tools/wiring.py)
│   ├── plugins/team-autobind.ts        chat.message hook
│   ├── tools/mail.ts                   mail_send/pull/done/status bridges
│   ├── tools/team.ts                   team_* bridges
│   └── package.json, package-lock.json, node_modules/
└── swarm-forge-tin/
    ├── harness.json                    wiring config (self-pointing)
    ├── ruff.toml                       lint select E4/E7/E9/F/I/UP
    ├── tools/                          harness executables
    │   ├── wiring.py                   config resolver: load(), state_root_for(), as_dict()
    │   ├── harness                     CLI: config / status / clean hot|state|artifacts|all
    │   ├── durable_store.py            locks, atomic JSON, sequences, run_cli()
    │   ├── mailbox.py                  durable inter-role mail CLI
    │   ├── team.py                     chunk/seat routing CLI
    │   ├── crap4py, dry4py, ruff4py    quality wrappers (artifacts via wiring)
    │   ├── gherkin-parser, gherkin-mutator, ir-dry-checker   APS wrappers
    │   └── aps/                        vendored Acceptance-Pipeline-Specification
    ├── harness_tests/                  harness self-tests
    │   ├── README.md, pytest.ini, conftest.py
    │   └── persistent/
    │       ├── support.py              shared test helper (env_without_swarm)
    │       ├── features/harness_wiring.feature        6 scenarios
    │       ├── acceptance/
    │       │   ├── runtime.py          World + scenario execution engine
    │       │   ├── steps.py            step handlers for harness_wiring.feature
    │       │   ├── generator.py        IR → pytest entrypoint + metadata
    │       │   └── run_acceptance.py   parse → dry → generate → pytest driver
    │       ├── unit/test_wiring.py                     16 tests
    │       ├── property/test_wiring_properties.py      4 hypothesis tests
    │       └── tools/
    │           ├── test_state_routing.py               3 mailbox/team state tests
    │           └── test_dry4py.py                      2 display_path regression tests
    ├── project_tests/                  src-project tests (pack-side variant)
    │   ├── README.md, pytest.ini, conftest.py
    │   └── persistent/{unit,property,features,acceptance}/.gitkeep
    ├── hot_tests/                      shared generated area (gitignored)
    │   ├── acceptance/                 generated entrypoint + metadata/
    │   └── mutation/                   reserved for gherkin-mutator runs
    └── dump/                           disposable artifacts (gitignored)
        ├── harness_wiring.json         parse IR
        ├── harness_wiring.dry.json     IR dry report
        ├── .coverage, coverage.lcov    coverage for crap4py
        ├── dry4py/jscpd-report.json    DRY report
        └── hypothesis/, pytest_cache/, ruff-cache/
```

## Wiring Config (`swarm-forge-tin/harness.json`)

```json
{
  "version": 1,
  "workspace_root": "..",
  "state_root": ".swarmforge",
  "artifacts_root": "dump",
  "hot_tests": "hot_tests",
  "persistent_tests": [
    { "root": "harness_tests/persistent", "pythonpath": ["."], "kind": "harness" },
    { "root": "project_tests/persistent", "pythonpath": ["."], "kind": "project" }
  ],
  "source_roots": ["tools"],
  "features": "harness_tests/persistent/features",
  "roles": ["orchestrator", "specifier", "coder", "refactorer", "architect", "mentor", "senior"]
}
```

Resolution order: `--config` > `SWARM_CONFIG` > nearest `harness.json` upward > pack
`harness.json` > defaults. Env overrides: `SWARM_WORKSPACE`, `SWARM_STATE_ROOT`,
`SWARM_HOT`, `SWARM_PACK`.

## Test Areas

| Area | Nature | Contents |
|---|---|---|
| `harness_tests/persistent/` | committed | 25 tests: unit 16, property 4, tools 5; one feature with 6 acceptance scenarios |
| `project_tests/persistent/` | committed, empty | pack-side home for src-project tests |
| `hot_tests/` | gitignored, regenerated | acceptance entrypoint + metadata (one file), mutation reserved |

Run commands:

```
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest   # 25 tests
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py    # 6 scenarios
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest  # empty
```

## Tooling Quick Reference

| Command | Purpose |
|---|---|
| `swarm-forge-tin/tools/harness status` | resolved pack/workspace/state/artifacts/hot/persistent paths |
| `swarm-forge-tin/tools/harness config` | same as JSON |
| `swarm-forge-tin/tools/harness clean hot\|state\|artifacts\|all [--force]` | shared-area cleanup; state refuses while items are in process |
| `swarm-forge-tin/tools/ruff4py <paths>` | lint (cache under `dump/ruff-cache`) |
| `swarm-forge-tin/tools/crap4py --source-root <src> --test-path <tests> [filter]` | CRAP report |
| `swarm-forge-tin/tools/dry4py --min-lines 4 <paths>` | DRY report |
| `swarm-forge-tin/tools/gherkin-parser <feature> <ir>` | Gherkin → JSON IR |
| `swarm-forge-tin/tools/ir-dry-checker <ir> <report>` | IR duplicate check |
| `swarm-forge-tin/tools/gherkin-mutator ...` | spec mutation (not yet wired to `hot_tests/mutation`) |
| `python3 swarm-forge-tin/tools/mailbox.py --root <ws> ...` | mail CLI (state via wiring) |
| `python3 swarm-forge-tin/tools/team.py --root <ws> ...` | team CLI (state via wiring) |

## Verification Status (2026-09-14)

- `pytest` persistent suite: **25 passed** (ruff clean on `tools` + `harness_tests/persistent`).
- Acceptance pipeline: **6/6 scenarios** passed from generated entrypoint in `hot_tests`.
- CRAP on `wiring.py` + `durable_store.py`: **0 functions above 10** (max 9.7, `find_config`).
- DRY on `tools` + `harness_tests`: **0 clones**.
- `harness clean hot` clears `hot_tests/` without touching persistent tests (proven by scenario 5).

## Disposable vs Persistent

- Disposable: `dump/` (all contents), `hot_tests/` (all contents), `__pycache__/`,
  `dump/ruff-cache/`, `dump/pytest_cache/`, `dump/hypothesis/`, `.swarmforge/` runtime state.
- Never delete: `harness_tests/persistent/`, `project_tests/persistent/`, `tools/`,
  `harness.json`, `harness_docs/`, `.opencode/`.
