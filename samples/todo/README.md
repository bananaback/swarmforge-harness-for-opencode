# Todo — a SwarmForge sample project

A tiny, self-contained Python project used to prove the pack runs against a
project other than itself (M6). This tree holds **source only**; the harness
assets for it live in the pack, never here.

## Layout

```
samples/todo/
└── src/todo.py        # the domain (TodoList)
```

Everything else is the pack's:

| Asset | Location |
|---|---|
| Wiring config | `swarm-forge-tin/harness.todo.json` |
| Authored tests + features + acceptance | `swarm-forge-tin/project_tests/persistent/` |
| Generated acceptance entry points | `swarm-forge-tin/hot_tests/` |
| Parse IR, coverage, quality reports | `swarm-forge-tin/dump/` |
| Mail + team durable state (shared) | `swarm-forge-tin/.swarmforge/` |

## Point the harness at this project

```bash
# resolved paths (workspace here; roots in the pack)
swarm-forge-tin/tools/harness --config swarm-forge-tin/harness.todo.json status

# unit + property tests
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# acceptance pipeline
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.todo.json
```

Switching between projects reuses the pack's shared `hot_tests/`, `dump/`, and
`.swarmforge/`; run `swarm-forge-tin/tools/harness clean all` before switching.

## Keeping the source tree clean

No harness artifact may land here — not tests, not reports, and not bytecode.
The pytest conftest and the acceptance runner set `sys.dont_write_bytecode`, so
the documented commands leave no `__pycache__` under `src/`. Any direct Python
run against the sample (for example a chunk oracle) must do the same:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ...
```

or set `PYTHONPYCACHEPREFIX` to the pack's `dump/` so bytecode caches land under
the artifacts root instead of next to the source.

