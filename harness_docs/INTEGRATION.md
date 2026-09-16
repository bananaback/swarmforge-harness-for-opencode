# Integrating SwarmForge Into Any Project

How to drop the SwarmForge harness next to a project you already have, point it
at that project by editing one file, and switch back and forth without leaving
anything behind. This is the practical companion to
[ARCHITECTURE.md](ARCHITECTURE.md) (wiring internals) and [WORKFLOW.md](WORKFLOW.md)
(roles and dispatch).

The wiring behavior described here is pinned by the `harness_wiring` and
`harness_cli` acceptance specs, so a regression is caught by the suite rather
than by reading this page.

## The Model In One Picture

```
anywhere/
├── my-project/            ← the project under work (source only, test-free)
│   └── src/
├── swarm-forge-tin/       ← the harness pack (copied)
│   ├── harness.json       ← THE single config file (the only thing you edit)
│   ├── tools/             ← harness CLIs
│   ├── project_tests/     ← authored tests for the wired project (pack-side)
│   ├── hot_tests/         ← generated entry points (disposable, in the pack)
│   ├── dump/              ← parse IR, reports, caches (disposable, in the pack)
│   └── .swarmforge/       ← mail + team durable state (in the pack)
├── .opencode/             ← the agent pack (copied)
├── AGENTS.md              ← the constitution (copied)
└── opencode.json          ← opencode config (copied)
```

Two rules make the whole thing portable:

1. **One config.** Every path the tools and roles use is resolved from
   `swarm-forge-tin/harness.json`. No path is hardcoded anywhere else.
2. **The pack owns the disposable areas.** `state_root`, `artifacts_root`, and
   `hot_tests` stay in the pack by default. The project holds only what you
   explicitly point a root at.

## 1. Copy The Harness Next To The Project

Copy these four items so the pack and the agent pack sit beside the project:

```
swarm-forge-tin/     # the harness pack
.opencode/           # agents, tool bridges, plugins
AGENTS.md            # the constitution
opencode.json        # opencode config
```

The pack does not have to be a sibling — only the paths in `harness.json` care
where the project is. Sibling layout keeps those paths short.

## 2. `harness.json` Is The Single Source Of Config

Every field is resolved relative to the config file (the pack), except
`pythonpath`, which is relative to its own `persistent_tests[].root`.

| Field | Meaning | Default |
|---|---|---|
| `workspace_root` | The project under work. | the pack's parent |
| `state_root` | Mail + team durable state. | `<workspace>/swarm-forge-tin/.swarmforge` |
| `artifacts_root` | Parse IR, dry reports, coverage, caches. | `<pack>/dump` |
| `hot_tests` | Generated acceptance entry points (disposable). | `<pack>/hot_tests` |
| `persistent_tests` | Authored tests, one entry per root: `{root, pythonpath, kind}`. | `[]` |
| `source_roots` | The project's source trees (quality tools scan these). | `["src"]` |
| `features` | The authored Gherkin root. | none |
| `roles` | The pipeline roles. | the eight-pack |

`kind` is what picks the root for a workspace: a pack-side config prefers the
`harness` root, a wired-project config prefers the `project` root. The choice is
config-driven and deterministic — it never probes the disk.

## 3. Choose Where The Persistent Tests Live

`persistent_tests[].root` is an ordinary path. Point it inside the pack, or
inside the project. Everything else (`state_root`, `artifacts_root`,
`hot_tests`) stays in the pack either way.

### Option A — tests in the pack (recommended; project tree stays test-free)

```json
"workspace_root": "../my-project",
"source_roots": ["../my-project/src"],
"persistent_tests": [
  { "root": "project_tests/persistent", "pythonpath": ["../../../my-project"], "kind": "project" }
],
"features": "project_tests/persistent/features"
```

The `pythonpath` entry points back at the project so tests can import its
source. `project_tests/persistent/` ships as an empty scaffold in exactly this
shape.

### Option B — tests inside the project

```json
"workspace_root": "../my-project",
"source_roots": ["../my-project/src"],
"persistent_tests": [
  { "root": "../my-project/tests/persistent", "pythonpath": ["../.."], "kind": "project" }
],
"features": "../my-project/tests/persistent/features"
```

Now the authored tests, features, and acceptance live in the project tree (that
is the point of the option). The **disposable** areas still do not: generated
entry points, parse IR, reports, and coverage all resolve to the pack's
`hot_tests/` and `dump/`. The pytest conftest and the acceptance runner set
`PYTHONDONTWRITEBYTECODE`, so no `__pycache__` is written next to the source.

Pick one; do not list both roots unless you are deliberately transitioning.

## 4. Point, Verify, And Switch

### First wiring

```bash
# resolve and print every path (exits 2 on a bad config)
swarm-forge-tin/tools/harness status

# run the project's unit + property tests
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# run its acceptance pipeline (parse -> dry -> generate -> run)
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.json
```

### Switching between self-hosting and a project

The switch is **editing the same few lines in `harness.json`**. To go from
self-hosting to a project:

| Line | Self-hosting | Wired project |
|---|---|---|
| `workspace_root` | `".."` | `"../my-project"` |
| `source_roots` | `["tools"]` | `["../my-project/src"]` |
| `persistent_tests` | `harness` + `project` roots | the project root |
| `features` | `harness_tests/persistent/features` | the project's features root |

Then clean the shared areas before running, so one project's generated entry
points cannot collide with another's:

```bash
swarm-forge-tin/tools/harness clean hot     # generated tests only
swarm-forge-tin/tools/harness clean all     # hot + artifacts + state (asks first if work is in process)
```

To switch back, restore the self-hosting lines and clean again. Editing one file
is the whole switch.

### Keeping two targets without editing

If you switch often, keep one config per target and select it — no edits:

```bash
swarm-forge-tin/tools/harness --config swarm-forge-tin/harness.myproject.json status
SWARM_CONFIG=swarm-forge-tin/harness.myproject.json python3 swarm-forge-tin/tools/harness status
```

`harness.json` remains the default when no `--config`/`SWARM_CONFIG` is given,
so the self-hosting story is unchanged.

## 5. Nothing Leaks Into The Project

By construction, the pack owns the disposable areas, and the project is only
written to if you point `persistent_tests[].root` inside it (Option B) or
`source_roots` at it for reading.

What is guaranteed:

- Generated entry points go to `hot_tests/` (pack).
- Parse IR, dry reports, coverage, and pytest/hypothesis caches go to
  `artifacts_root` (pack).
- Mail and team state go to `state_root` (pack).
- Bytecode is suppressed: the acceptance runner exports
  `PYTHONDONTWRITEBYTECODE=1`, the pytest conftest sets
  `sys.dont_write_bytecode`, and `team.py`'s oracle runner does the same. For
  any manual Python run against the project, prefix
  `PYTHONDONTWRITEBYTECODE=1` or set `PYTHONPYCACHEPREFIX` to the pack's `dump/`.

The `harness_portability` contract snapshots a wired project tree, runs the
pipeline, and fails on any added, removed, or changed file. The committed spec
and sample were retired before ship; `project_tests/persistent/` keeps the
scaffold the contract exercises.

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `harness: cannot read config ...` | Bad path or malformed JSON | Fix `harness.json`; `harness status` names the file. |
| Wrong workspace resolved | A stale `SWARM_CONFIG`/`SWARM_WORKSPACE`/`SWARM_PACK` env var overrides the file | Unset the `SWARM_*` override. |
| Generated tests collide across projects | The shared `hot_tests/` still holds the previous project's entry points | `harness clean hot` before switching. |
| `__pycache__` appears in the project | A Python run without the bytecode guard | Use `PYTHONDONTWRITEBYTECODE=1`, or `PYTHONPYCACHEPREFIX=<pack>/dump`. |
| `run_acceptance: pass --config` | The project acceptance runner needs the config explicitly | Pass `--config swarm-forge-tin/harness.json` or set `SWARM_CONFIG`. |

## 7. What Is Portable And What Is Not

- **Portable:** the pack, `.opencode/`, `AGENTS.md`, and `opencode.json` — copy
  them anywhere and edit `harness.json`.
- **Disposable (never commit, safe to delete):** `hot_tests/`, `dump/`,
  `.swarmforge/`.
- **Never delete:** `<pack>/harness_tests/persistent/` (the harness's own
  tests).
- **Project-side:** `source_roots` is read-only to the harness; only Option B's
  persistent root is authored inside the project.
