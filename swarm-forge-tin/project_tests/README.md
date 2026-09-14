# Project Tests

Pack-side home for the src project's persistent tests. Use this when the project tests
live with the pack instead of the project tree; the alternative is a persistent root
inside the project itself, configured in `harness.json`.

Authored tests only, committed. Generated tests never land here — they go to
`swarm-forge-tin/hot_tests/`, the shared area cleaned on project switch.

## Layout

```
project_tests/
├── pytest.ini          # testpaths = persistent; pythonpath: persistent, ../../src
├── conftest.py         # no bytecode; hypothesis storage → ../dump/hypothesis-project
└── persistent/
    ├── unit/           # TDD unit tests
    ├── property/       # hypothesis properties
    ├── features/       # authored Gherkin specs
    └── acceptance/     # step handlers + runtime
```

## Running

```
cd swarm-forge-tin/project_tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
```

## Wiring

`harness.json` lists this persistent root as
`{ "root": "project_tests/persistent", "pythonpath": ["."], "kind": "project" }`.
`swarm-forge-tin/tools/harness status` reports whether it exists; `harness config`
prints the resolved path.
