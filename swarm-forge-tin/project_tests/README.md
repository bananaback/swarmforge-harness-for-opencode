# Project Tests

Pack-side home for the wired project's persistent tests. The project source
lives outside the pack (`samples/<name>/src`); everything the harness authors or
generates for it lives here or in the pack's shared areas.

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

## Wiring

`swarm-forge-tin/harness.todo.json` points at the sample project:

- `workspace_root` → `../samples/todo` (source only, test-free)
- `persistent_tests` → `project_tests/persistent` (this root, `kind: project`)
- `features` → `project_tests/persistent/features`
- `state_root` / `artifacts_root` / `hot_tests` → the pack's shared areas

## Running

```bash
# unit + property
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# acceptance (parse → dry → generate → run), project chosen by the config
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.todo.json
```
