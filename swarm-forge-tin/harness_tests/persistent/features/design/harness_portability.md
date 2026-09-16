# Design seed: harness portability

## TASK

Feature: `harness_tests/persistent/features/harness_portability.feature`
(task `harness-portability`).

Scope this design covers: the `harness.json` config contract that lets a config
choose project-vs-pack persistent tests, the wiring interface that resolves and
selects them, and the acceptance step handlers that make the five portability
scenarios executable in the harness suite.

Out of scope: changing `wiring.py`, `team.py`, the sample project, the todo
config, or the project acceptance pipeline. All of those already satisfy the
feature (validated: config switching, kind selection, shared roots in pack,
project pipeline exit 0, sample tree unchanged). The only new production of
code is one acceptance step module plus its registration.

## DEFINITION OF DONE

- [ ] every noun with identity is a class; every noun without identity is a frozen value object
- [ ] no decision about an object's state is made by code outside that object
- [ ] every constructor validates its inputs and raises on invalid state
- [ ] no class has more than one reason to change
- [ ] no Protocol forces an unused method on any implementer
- [ ] every real volatility has a named Strategy with a stated injection point, or is marked `none`
- [ ] no domain class varies behavior by subclassing
- [ ] no call chain goes more than one dot past self, a parameter, or a local
- [ ] every external dependency is named as a Protocol before any concrete implementation
- [ ] every lookup raises a specific exception or returns a real value; nothing returns `None`
- [ ] every method is a command or a query in the interface contract, never both
- [ ] no method takes a boolean parameter that changes its behavior
- [ ] every Strategy, Protocol, and adapter named in phases 2-3 appears in the contract -- nothing promised earlier is dropped
- [ ] no value object or wrapper class exists that adds no validation or unit safety over the primitive it wraps

## INTERFACE CONTRACT

### Existing config contract (`harness.json`) -- no change

The config document is the chooser for project-vs-pack persistent tests: it
lists each authored test root and labels it with a `kind`.

```
{
  "version": 1,
  "workspace_root": "<path, relative to the config file's directory>",
  "state_root": "<path>",
  "artifacts_root": "<path>",
  "hot_tests": "<path>",
  "persistent_tests": [
    {
      "root": "<path, relative to the config file's directory>",
      "pythonpath": ["<path, relative to this root>"],
      "kind": "harness" | "project"
    }
  ],
  "source_roots": ["<path>"],
  "features": "<path>",
  "roles": ["<role>", ...]
}
```

Rules the feature pins:
- A `project`-kind root holds the wired project's tests; a `harness`-kind root
  holds the pack's own tests. A config may declare both.
- Relative paths resolve against the config's directory; each `pythonpath`
  entry resolves against its own root.
- The shared areas (`state_root`, `artifacts_root`, `hot_tests`) point back into
  the pack for a pack-side config, so switching projects never writes the
  project tree.
- Fixture `harness.todo.json`: `workspace_root` = `../samples/todo`,
  `source_roots` = `../samples/todo/src`, one `persistent_tests` entry
  `{root: project_tests/persistent, pythonpath: [../../../samples/todo], kind:
  project}`, `features` = `project_tests/persistent/features`, shared roots =
  pack. Fixture `harness.json`: `workspace_root` = `..`, roots in the pack.

### Existing wiring interface (`tools/wiring.py`) -- no change

```
@dataclass(frozen=True)
class Wiring:
    pack_root: Path
    workspace_root: Path
    state_root: Path
    artifacts_root: Path
    hot_tests: Path
    persistent_tests: tuple   # of {"root": Path, "pythonpath": tuple[Path, ...], "kind": str}
    source_roots: tuple
    features: Path | None
    roles: tuple
    config_path: Path | None

    def as_dict(self) -> dict: ...

class WiringError(Exception): ...

def load(config: str | Path | None = None, start: str | Path | None = None) -> Wiring: ...
def clear_cache() -> None: ...
def find_config(start=None) -> Path | None: ...
def state_root_for(workspace, override=None) -> Path: ...
```

### Existing selection interface (`tools/team.py`) -- no change

```
def persistent_test_root(resolved) -> Path | None: ...
```

Selection rule (single owner, already implemented and covered by
`harness_wiring` 12/13): config lives in the pack -> prefer `harness` then
`project`; otherwise prefer `project` then `harness`; no entries -> `None`.
The portability steps do not reimplement it; scenario 2 reuses the existing
`the persistent test root is selected` handler in `wiring_steps.py`.

### Existing acceptance interface (`acceptance/runtime.py`) -- no change

```
class World:
    def __init__(self) -> None: ...        # self.state: dict[str, Any]

StepHandler = Callable[[World, dict[str, str]], None]

class Runtime:
    def register(self, pattern: str, handler: StepHandler) -> None: ...
    def run_scenario(self, scenario: dict, background: list[dict] | None = None) -> None: ...
    def run_all(self, ir: dict) -> None: ...
```

### New module (`acceptance/steps/harness_portability_steps.py`)

```
PACK: Path            # wiring.PACK_ROOT
TODO_CONFIG: Path     # PACK / "harness.todo.json"
TODO_SAMPLE: Path     # PACK.parent / "samples" / "todo"
PROJECT_RUNNER: Path  # PACK / "project_tests" / "persistent" / "acceptance" / "run_acceptance.py"

def _pack_configs(world: World, examples: dict[str, str]) -> None: ...
def _load_through_config(world: World, examples: dict[str, str]) -> None: ...
def _resolved_workspace(world: World, examples: dict[str, str]) -> None: ...
def _project_with_persistent_location(world: World, examples: dict[str, str]) -> None: ...
def _load_wired_config(world: World, examples: dict[str, str]) -> None: ...
def _selected_inside(world: World, examples: dict[str, str]) -> None: ...
def _todo_wired(world: World, examples: dict[str, str]) -> None: ...
def _todo_resolved(world: World, examples: dict[str, str]) -> None: ...
def _resolved_area_in_pack(world: World, examples: dict[str, str]) -> None: ...
def _pipeline_runs(world: World, examples: dict[str, str]) -> None: ...
def _pipeline_passes(world: World, examples: dict[str, str]) -> None: ...
def _sample_snapshot(world: World, examples: dict[str, str]) -> None: ...
def _sample_unchanged(world: World, examples: dict[str, str]) -> None: ...

HANDLERS: list[tuple[str, StepHandler]]
```

Handler / pattern / world-state contract (every handler returns `None`; a
handler that fails raises `AssertionError`):

| Handler | Pattern | Kind | Reads | Writes |
|---|---|---|---|---|
| `_pack_configs` | `^the harness pack holds its own config and the todo config$` | command | `wiring.PACK_ROOT` | `pack`, `configs` |
| `_load_through_config` | `^wiring is loaded through the (.+) config$` | command | `configs` | `resolved` |
| `_resolved_workspace` | `^the resolved workspace is the (.+)$` | query | `resolved`, `pack` | -- |
| `_project_with_persistent_location` | `^a temporary project whose config places its persistent root in the (.+)$` | command | -- | `config_path`, `pack`, `location_dirs` |
| `_load_wired_config` | `^the wired config is loaded$` | command | `config_path` | `resolved` |
| `_selected_inside` | `^the selected persistent root is inside the (.+)$` | query | `selected_persistent`, `location_dirs` | -- |
| `_todo_wired` | `^the todo sample wired through the pack todo config$` | command | `wiring.PACK_ROOT` | `pack`, `todo_config` |
| `_todo_resolved` | `^the todo config is resolved$` | command | `todo_config` | `resolved` |
| `_resolved_area_in_pack` | `^the resolved (.+) path is inside the harness pack$` | query | `resolved`, `pack` | -- |
| `_pipeline_runs` | `^the todo sample acceptance pipeline runs$` | command | `todo_config` | `pipeline_result` |
| `_pipeline_passes` | `^the todo sample acceptance pipeline passes$` | query | `pipeline_result` | -- |
| `_sample_snapshot` | `^the todo sample is snapshotted$` | command | `todo_config` | `sample_root`, `sample_snapshot` |
| `_sample_unchanged` | `^no file appears or changes under the todo sample$` | query | `sample_root`, `sample_snapshot` | -- |

World-state keys (all set by the module above, except `selected_persistent`):
`pack: Path`; `configs: dict[str, Path]` keyed `pack`/`todo`; `resolved:
Wiring`; `config_path: Path`; `location_dirs: dict[str, Path]` keyed
`project`/`pack`; `selected_persistent: Path`; `todo_config: Path`;
`pipeline_result: subprocess.CompletedProcess`; `sample_root: Path`;
`sample_snapshot: dict[str, str]` (relative path -> sha256 hex).

Behaviour each handler must produce:
- `_pack_configs`: `pack = wiring.PACK_ROOT`; assert `pack/harness.json` and
  `pack/harness.todo.json` both exist; record them under `configs`.
- `_load_through_config`: `wiring.clear_cache()`; `resolved =
  wiring.load(config=configs[name])`.
- `_resolved_workspace`: expected = `pack.parent` for `pack parent`,
  `TODO_SAMPLE` for `todo sample`; assert `resolved.workspace_root == expected`.
  Registered after `wiring_steps`, so the existing `pack parent` handler serves
  that wording and this handler serves `todo sample`.
- `_project_with_persistent_location`: build a temp root with `project/` and a
  valid `pack/` (contains `tools/wiring.py`); for `pack` location set
  `SWARM_PACK` to the temp pack and place the root at `pack/tests`, for
  `project` location place it at `project/tests`; write a one-entry config at
  `project/harness.json` (`workspace_root: "."`, the root, `kind: "project"`).
  Record `config_path`, `pack`, and `location_dirs = {project, pack}`.
- `_load_wired_config`: `wiring.clear_cache()`; `resolved =
  wiring.load(config=config_path)`.
- `_selected_inside`: assert `selected_persistent` is not `None`; assert
  `Path(selected_persistent).is_relative_to(location_dirs[location])`.
- `_todo_wired`: assert `TODO_CONFIG` is a file; record `pack` and `todo_config`.
- `_todo_resolved`: `wiring.clear_cache()`; `resolved =
  wiring.load(config=todo_config)`.
- `_resolved_area_in_pack`: map `artifacts` -> `artifacts_root`, `hot` ->
  `hot_tests`, `state` -> `state_root`; assert the value is not `None` and
  `is_relative_to(pack)`.
- `_pipeline_runs`: make a temp hot dir with `common._temp_root()/hot`; run
  `[sys.executable, PROJECT_RUNNER, "--config", todo_config]` with `cwd=PACK`,
  an environment stripped of `SWARM_*` plus `PYTHONDONTWRITEBYTECODE=1` and
  `SWARM_HOT=<temp hot>`, captured text. Record the `CompletedProcess`. The
  `SWARM_HOT` override is the injection point that keeps the shared
  `hot_tests/` from colliding with the running harness entry points (the
  documented module-name clash on `runtime`/`steps`).
- `_pipeline_passes`: assert `pipeline_result.returncode == 0`, including
  stdout and stderr in the failure message.
- `_sample_snapshot`: `root = wiring.load(config=todo_config).workspace_root`;
  snapshot every file under `root` as `relative path -> sha256(bytes)`.
- `_sample_unchanged`: re-snapshot and assert equality; on mismatch report the
  added, removed, and changed relative paths.

Registration: `acceptance/steps/__init__.py` imports
`HANDLERS as _PORTABILITY_HANDLERS` from `.harness_portability_steps` and
appends `*_PORTABILITY_HANDLERS` to `STEP_HANDLERS` after `_WIRING_HANDLERS`.

## FILES

- `swarm-forge-tin/harness_tests/persistent/acceptance/steps/harness_portability_steps.py` -- new; the 13 handlers above and `HANDLERS`; imports `wiring`, `runtime.World`, and `_temp_root`/`step_values` from `.common`; called by the generated portability entry point via `steps.STEP_HANDLERS`.
- `swarm-forge-tin/harness_tests/persistent/acceptance/steps/__init__.py` -- register `_PORTABILITY_HANDLERS` after `_WIRING_HANDLERS`; the generated entry point imports `STEP_HANDLERS` from here.
- `swarm-forge-tin/harness_tests/persistent/acceptance/steps/wiring_steps.py` -- verify only; its `_select_persistent_root` handler and `_pack`/`_resolved` helpers are reused by scenario 2, so `world.state["resolved"]` and `world.state["pack"]` must be the keys it reads.
- `swarm-forge-tin/harness.todo.json` -- config fixture; verify only (workspace `../samples/todo`, one project-kind root in the pack, shared roots in the pack); change only if a scenario fails.
- `swarm-forge-tin/harness.json` -- pack config fixture; verify only (workspace pack parent, harness-kind root).
- `swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py` -- invoked by `_pipeline_runs`; verify only.
- `swarm-forge-tin/project_tests/persistent/acceptance/steps/__init__.py` -- the todo step registration the pipeline subprocess imports; verify only.
- `swarm-forge-tin/samples/todo/src/todo.py` -- sample domain; read-only fixture; never written.
- `swarm-forge-tin/tools/wiring.py` -- no change; the config and resolution contract above is already implemented.
- `swarm-forge-tin/tools/team.py` -- no change; `persistent_test_root` stays the selection owner.
- `swarm-forge-tin/harness_tests/persistent/acceptance/steps/common.py` -- no change; reuse `_temp_root` and `step_values`.

## VOLATILITY

none. The feature pins exactly one committed sample (`samples/todo`) and its
pack-side config; the sample path, config path, and pipeline runner are
constants. The one real rule in this domain -- which persistent root a
workspace runs from -- already has a single owner, `persistent_test_root`, and
the feature does not add a second case for it. No Strategy is manufactured.

## SELF-AUDIT

- [x] every noun with identity is a class; every noun without identity is a frozen value object -- `Wiring` (a resolved config) is the existing frozen dataclass; `World` is the existing per-scenario class; persistent entries and the sample snapshot are value objects (tuples/dicts), so the design adds no class.
- [x] no decision about an object's state is made by code outside that object -- the handlers assert resolved values and delegate the one state-dependent choice to `persistent_test_root`, the single owner; they never branch on `Wiring` fields to pick behaviour.
- [n/a] every constructor validates its inputs and raises on invalid state -- no new class or constructor is introduced; the existing `wiring.load` raises `WiringError` on a missing, unreadable, malformed, or rootless config.
- [x] no class has more than one reason to change -- the new module has one reason (the portability feature's steps); each handler owns exactly one step shape.
- [x] no Protocol forces an unused method on any implementer -- no Protocol is introduced; `StepHandler` is the existing two-argument callable every module already implements.
- [x] every real volatility has a named Strategy with a stated injection point, or is marked `none` -- VOLATILITY is `none`; the one rule is owned by `persistent_test_root` and has no second case in this feature.
- [x] no domain class varies behavior by subclassing -- the design introduces no inheritance; handlers are plain functions in one `HANDLERS` list.
- [x] no call chain goes more than one dot past self, a parameter, or a local -- handlers read `resolved.workspace_root`, `result.returncode`, `path.is_relative_to(pack)`, and `world.state[...]`, each one dot past a local or a parameter.
- [n/a] every external dependency is named as a Protocol before any concrete implementation -- the design adds no domain dependency; `_pipeline_runs` invokes the existing pipeline as a subprocess, exactly as the other step modules do.
- [x] every lookup raises a specific exception or returns a real value; nothing returns `None` -- `_selected_inside` and `_resolved_area_in_pack` assert non-`None` before use; unknown names raise `KeyError` from the name map; the only `None`-returning lookup is the pre-existing `persistent_test_root`, which the feature does not alter.
- [x] every method is a command or a query in the interface contract, never both -- the table's Kind column marks the `Given`/`When` handlers command and the `Then` handlers query; no handler both mutates `world.state` and asserts.
- [x] no method takes a boolean parameter that changes its behavior -- every handler takes `(world, examples)` only; `location` and `area` are string selectors that pick a fixture or a field, not boolean flags.
- [x] every Strategy, Protocol, and adapter named in phases 2-3 appears in the contract -- phases 2-3 name none, so nothing is dropped; the contract lists every handler, pattern, and world key.
- [x] no value object or wrapper class exists that adds no validation or unit safety over the primitive it wraps -- the design introduces no wrapper; the snapshot is a plain dict and the selected root is a `Path`.

Caveats (not checklist items):
- `_resolved_workspace` uses `^the resolved workspace is the (.+)$`, which also
  matches the existing `the resolved workspace is the pack parent` wording.
  Registration order (portability appended after `wiring_steps`) leaves that
  wording with the existing handler, which needs `world.state["pack"]`; the
  portability `Given` sets it. The coder must keep the append order.
- `_pipeline_runs` relies on `SWARM_HOT` isolation; without it the project
  pipeline would collect the running harness entry points and recurse.
- Scenarios 4 and 5 run a nested pytest, so they are the slowest tests in the
  suite and depend on the project pipeline staying green.
