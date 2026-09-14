# Harness Tests

Self-tests for the SwarmForge harness tooling (`swarm-forge-tin/tools/`), not the host
project. Sibling areas: `project_tests/` is the pack-side home for src-project persistent
tests, and `hot_tests/` is the shared generated area.

## Wiring

Paths come from `swarm-forge-tin/harness.json` (nearest upward, or `SWARM_CONFIG` /
`SWARM_PACK`). `swarm-forge-tin/tools/harness status` prints the resolved paths;
`swarm-forge-tin/tools/harness config` prints them as JSON.

## Areas

| Area | Nature | Committed | Contains |
|---|---|---|---|
| `harness_tests/persistent/` | authored harness self-tests | yes | unit, property, features, acceptance steps, tools |
| `project_tests/persistent/` | authored src-project tests | yes | unit, property, features, acceptance steps |
| `hot_tests/` | generated, shared | no | generated acceptance entrypoints, mutants |

Principle: persist authored inputs; regenerate hot outputs. Deleting `hot_tests/` must
never delete a persistent test. `hot_tests/` is gitignored via `swarm-forge-tin/hot_tests/`
in the root `.gitignore`.

## Layout

```
swarm-forge-tin/
├── harness_tests/              # harness self-tests
│   ├── pytest.ini              # testpaths = persistent; pythonpath adds ../tools
│   ├── conftest.py             # no bytecode; hypothesis storage → ../dump/hypothesis
│   └── persistent/
│       ├── unit/
│       ├── property/
│       ├── features/
│       ├── acceptance/
│       └── tools/
├── project_tests/              # src-project tests (pack-side variant)
│   ├── pytest.ini
│   ├── conftest.py
│   └── persistent/{unit,property,features,acceptance}
└── hot_tests/                  # shared generated area
    ├── acceptance/
    └── mutation/
```

## Running

```
cd swarm-forge-tin/harness_tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest                    # harness tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/unit    # one kind
```

Hot tests run from the shared area after regeneration:

```
cd swarm-forge-tin/hot_tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest acceptance
```

Acceptance pipeline (parse → dry-check → generate → run generated tests):

```
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py
```

Project tests run from their own root:

```
cd swarm-forge-tin/project_tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
```

## Switching Projects

- `swarm-forge-tin/tools/harness clean hot` clears the shared generated area; add
  `state`, `artifacts`, or `all` to clear those too. `clean state` refuses while mail or
  team items are in process unless `--force` is passed.
- Point the harness at another project with `SWARM_CONFIG=/path/to/harness.json`, or by
  editing `workspace_root` in `harness.json`.

## Rules

- No host-project imports: tests build temp project roots under pytest's `tmp_path`.
- No live state: tests touch only pytest temp roots, never the real project or
  `.swarmforge/`.
- Optional toolchains degrade: bb/APS-dependent checks skip cleanly when `bb` or
  coverage tooling is absent.
- Artifacts stay out of the tree: quality reports and caches go to the configured
  artifacts root.
