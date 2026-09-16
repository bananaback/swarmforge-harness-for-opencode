# Project Tests

Pack-side home for a wired project's persistent tests. The project source lives
outside the pack; everything the harness authors or generates for it lives here
or in the pack's shared areas.

This root is an empty scaffold: it ships with the structure in place and no
authored tests. A pack-side config points at a project and fills it.

## Layout

```
project_tests/
├── pytest.ini          # testpaths = persistent; pythonpath: persistent, the project root
├── conftest.py         # no bytecode; hypothesis storage → ../dump/hypothesis-project
└── persistent/
    ├── unit/           # TDD unit tests
    ├── property/       # hypothesis properties
    ├── features/       # authored Gherkin specs (+ design/ seeds)
    └── acceptance/     # step handlers + runtime + generator + runner
```

`acceptance/` ships the runtime, generator, and runner; `steps/__init__.py`
starts as an empty `STEP_HANDLERS` registry to fill per project.

## Wiring

A pack-side config points `workspace_root` at the project (source only,
test-free) and `persistent_tests` at `project_tests/persistent` with
`kind: project`; `state_root` / `artifacts_root` / `hot_tests` stay in the pack's
shared areas. See
[harness_docs/INTEGRATION.md](../../harness_docs/INTEGRATION.md).

## Running

```bash
# unit + property
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# acceptance (parse → dry → generate → run), project chosen by the config
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.json
```
