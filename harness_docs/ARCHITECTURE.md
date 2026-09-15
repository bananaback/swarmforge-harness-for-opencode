# Architecture

How the SwarmForge harness is put together: the pack, its wiring, the durable
state layout, and the storage primitives the tools share.

- Tools and their operation contracts: [TOOLS.md](TOOLS.md)
- Roles and process: [WORKFLOW.md](WORKFLOW.md)
- Tests and pipelines: [TESTING.md](TESTING.md)

## Self-Hosting Shape

The pack (`swarm-forge-tin/`) is a normal tool directory that happens to point at
this repository. `swarm-forge-tin/harness.json` sets `workspace_root = ".."` and
`source_roots = ["tools"]`, so "the project under work" is the repository and
"the source" is the harness CLIs themselves. The same pack runs unchanged
against a production project by pointing at a different config.

Three ideas carry the whole design:

1. **One config seam.** Every path a tool or role needs comes from
   `harness.json` (or an environment override). Nothing hardcodes
   `swarm-forge-tin/` or `src/`.
2. **Durable state is the source of truth.** Mail and chunk work are files on
   disk, not message contents. A wake line carries no task; the recipient pulls
   the durable record.
3. **Authored vs. generated.** Persistent tests and specs are committed;
   generated entry points, artifacts, and caches are disposable and rebuilt.

## Repository Layout

```
harness_research/
├── AGENTS.md                          constitution / opencode instructions
├── opencode.json                      default model, model variants, instructions
├── .gitignore                         bytecode, caches, state, hot_tests, dump
├── .opencode/                         the agent pack
│   ├── agents/                        orchestrator, specifier, designer,
│   │                                  task-breaker, coder, refactorer,
│   │                                  architect, mentor
│   ├── lib/wiring.ts                  TS wiring resolver (mirrors tools/wiring.py)
│   ├── lib/team-autobind.ts           seat auto-bind core (pure)
│   ├── plugins/team-autobind.ts       chat.message hook that calls the core
│   ├── tools/mail.ts                  mail_* bridges -> mailbox.py
│   └── tools/team.ts                  team_* bridges -> team.py
├── harness_docs/                      this documentation
│   ├── README.md  ARCHITECTURE.md  TOOLS.md  WORKFLOW.md  TESTING.md  ROADMAP.md
│   └── examples/                      annotated payloads and journal
└── swarm-forge-tin/                   the harness pack
    ├── harness.json                   wiring config (self-pointing)
    ├── ruff.toml                      lint rules (E4/E7/E9/F/I/UP)
    ├── tools/
    │   ├── wiring.py                  config resolver + Wiring dataclass
    │   ├── harness                    CLI: config / status / clean
    │   ├── durable_store.py           locks, atomic JSON, sequences, run_cli
    │   ├── mailbox.py                 durable inter-role mail CLI
    │   ├── team.py                    chunk/seat routing, journal, attempts
    │   ├── taskbreak.py               task-breaker plan -> team_open bridge
    │   ├── crap4py dry4py ruff4py     quality wrappers (artifacts via wiring)
    │   ├── gherkin-parser             bash wrapper -> bb APS task
    │   ├── gherkin-mutator            bash wrapper (folds --level full -> hard)
    │   ├── ir-dry-checker             bash wrapper -> bb APS task
    │   └── aps/                       vendored Acceptance-Pipeline-Specification
    ├── harness_tests/                 harness self-tests (committed)
    │   ├── pytest.ini conftest.py README.md
    │   └── persistent/                unit/ property/ features/ acceptance/ tools/
    ├── project_tests/                 src-project tests, pack-side (committed)
    │   ├── pytest.ini conftest.py README.md
    │   └── persistent/{unit,property,features,acceptance}/
    ├── hot_tests/                     generated tests (gitignored, disposable)
    │   ├── acceptance/                generated entry points + metadata/
    │   └── mutation/<stem>/           feature copy, base IR, mutants, work
    └── dump/                          reports and caches (gitignored, disposable)
        ├── <feature>.json             parse IR
        ├── <feature>.dry.json         IR dry report
        ├── mutation/<stem>.json       mutation report
        ├── .coverage coverage.lcov    coverage for crap4py
        ├── dry4py/jscpd-report.json   DRY report
        └── hypothesis/ pytest_cache/ ruff-cache/
```

## Wiring

### Config (`harness.json`)

Committed at `<pack>/harness.json`, or found upward from the working directory,
or pointed at explicitly. Schema v1:

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
  "roles": ["orchestrator", "specifier", "designer", "task-breaker",
            "coder", "refactorer", "architect", "mentor"]
}
```

Relative paths are resolved against the config file's directory (or `~/...`).
`pythonpath` entries are resolved relative to their persistent root, not the
config.

| Field | Meaning |
|---|---|
| `workspace_root` | Project the roles work on; the `--root` handed to mailbox/team |
| `state_root` | Where live mail and task state live |
| `artifacts_root` | Quality reports, coverage, caches (`dump/`) |
| `hot_tests` | Shared generated test area; cleaned on project switch |
| `persistent_tests` | Authored test roots: `root`, `pythonpath` (relative to root), `kind` |
| `source_roots` | Default paths for crap4py/dry4py/ruff4py when no args are given |
| `features` | Gherkin feature root for the acceptance pipeline |
| `roles` | Role list for mailbox discovery when `.opencode/agents` is absent |

`kind` is `harness` or `project`. It lets `team.py` choose the right persistent
root without stat-ing the disk (see [persistent test root](#persistent-test-root-kind)).

### Resolution Order (Python, `tools/wiring.py`)

1. `SWARM_CONFIG` environment variable — must point at an existing file, else a
   `WiringError`.
2. Nearest `harness.json` walking up from the start directory, checking both
   `<dir>/harness.json` and `<dir>/swarm-forge-tin/harness.json`.
3. `SWARM_PACK` environment variable → `<pack>/harness.json`.
4. `<pack>/harness.json` (pack inferred from the location of `tools/wiring.py`).
5. `~/.config/swarm-forge/harness.json`.
6. No config → built-in defaults.

The pack root is the config's directory when it contains `tools/wiring.py`;
otherwise it is the running `wiring.py`'s pack. `SWARM_PACK` overrides.

Defaults when a field is absent: workspace = pack's parent; state =
`<workspace>/swarm-forge-tin/.swarmforge`; artifacts = `<pack>/dump`; hot =
`<pack>/hot_tests`; sources = `<config dir>/src`; roles = the eight-role default.

### Environment Overrides

| Variable | Overrides |
|---|---|
| `SWARM_CONFIG` | Config file location |
| `SWARM_PACK` | Pack root |
| `SWARM_WORKSPACE` | Workspace root |
| `SWARM_STATE_ROOT` | State root |
| `SWARM_HOT` | Hot tests root |

### Test Areas And Isolation

| Area | Nature | Committed |
|---|---|---|
| `harness_tests/persistent/` | harness self-tests | yes |
| `project_tests/persistent/` | src-project tests, pack-side variant | yes |
| `hot_tests/` | shared generated tests and run state | no |

- Each persistent root is its own pytest rootdir with its own `pythonpath` and
  cache; harness tests never collect project tests and vice versa. The actual
  import path is set in that root's `pytest.ini`; the config's `pythonpath` is
  resolved and reported by wiring.
- `hot_tests/` is never committed and is cleaned on project switch.
- Project tests may instead live in the project tree; point `persistent_tests`
  at that root.

### Persistent Test Root (kind)

`team.py` must decide which configured root holds "this workspace's tests".
`persistent_test_root()` uses `kind`, never a disk probe:

- Config belongs to the pack (self-hosted) → prefer `harness`, then `project`.
- Otherwise → prefer `project`, then `harness`.

That root is what the deterministic payload's RESOLVED PATHS reports.

### Per-Tool Path Mapping

| Tool | Wiring use |
|---|---|
| `wiring.py` | Loads `harness.json`, resolves paths, exposes the `Wiring` dataclass |
| `harness` | `config` / `status` / `clean hot\|state\|artifacts\|all [--force]` |
| `mailbox.py`, `team.py` | State root via wiring or `--state-root` |
| `taskbreak.py` | Artifacts root via wiring for staged chunk inputs; opens via `team open` |
| `crap4py` | Coverage under `artifacts_root` (`COVERAGE_FILE`, LCOV) |
| `dry4py` | Report under `artifacts_root/dry4py` |
| `ruff4py` | Cache under `artifacts_root/ruff-cache`; config default `<pack>/ruff.toml` |
| `gherkin-parser`, `ir-dry-checker`, `gherkin-mutator` | Inputs/outputs are arguments; no path discovery |
| `.opencode/lib/wiring.ts` | Shared resolver for `mail.ts`, `team.ts`, `team-autobind.ts` |

### Project Profiles

Harness development (this repo) — self-hosting:

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
  "persistent_tests": [{ "root": "tests", "pythonpath": ["."], "kind": "project" }],
  "hot_tests": "~/.cache/swarm-forge/hot" }
```

Switch by editing `harness.json`, or without touching it via
`SWARM_CONFIG=/path/to/other.json`.

### `harness` CLI

```
harness config                 # resolved wiring as JSON
harness status                 # resolved paths and existence markers
harness clean [TARGET]         # hot (default) | state | artifacts | all
harness clean state --force    # clean even while items are in process
```

- `clean` empties the target directory's contents (creating it if missing); it
  never removes the directory itself.
- `clean state` refuses (exit 2) when mail/team items are in process unless
  `--force`.
- All resolve via `--config` / `--workspace` or the environment.

## Durable Store (`tools/durable_store.py`)

Shared primitives so each tool does not reimplement storage:

| Function | Purpose |
|---|---|
| `iso_now()` | UTC timestamp `YYYY-MM-DDTHH:MM:SSZ` |
| `lock(lock_dir, name)` | Exclusive `fcntl.flock` advisory lock over `<name>.lock` |
| `write_json_atomic(path, doc)` | Write to a temp file, fsync, `os.replace` |
| `read_json`, `list_json` | Read one file; sorted non-dot `.json` files in a dir |
| `next_seq(path)` | Read/increment/write a monotonic counter file |
| `run_cli(...)` | Parse argv, resolve `--root`, dispatch, render tool errors (exit 2) |

## State Layout

Live work is grouped by task open date (UTC); each task is one self-contained
folder; each chunk is one role's turn.

```
<state_root>/
  mail/                                    # handoffs between roles (see TOOLS.md)
  tasks/                                   # live work
    2026-09-14/                            # date folder = task open day (UTC)
      feature/                             # a task may be nested under a path
        periods/                           #   task: feature/periods
          task.json                        #   who/what/when + resolved config facts
          01-coder/                        #   chunk: <NN>-<role>
            input/                         #   write-once copies of the given inputs
              brief.md  periods.feature  periods.json  design.md
            journal.jsonl                  #   append-only, one JSON entry per line
            output/                        #   oracle attempt artifacts
              attempt-01.txt  attempt-01.diff  .seq
          02-refactorer/                   #   same shape
          03-architect/
    2026-09-15/
  done/                                    # preserved tasks, mirrored date layout
    2026-09-14/feature/periods/
  .locks/                                  # team locks (hashed names)
```

Rules:

- A task folder holds only `task.json` and chunk folders.
- A chunk folder holds only `input/`, `journal.jsonl`, and `output/`.
- `input/` is write-once; `journal.jsonl` only grows; nothing is hand-edited.

### `task.json`

Written by `team.py open`. Key fields:

| Field | Meaning |
|---|---|
| `task` | Task name |
| `created_at` | Open timestamp (UTC) |
| `role` | Role that opened the first chunk |
| `chunk` | First chunk name, `01-<role>` |
| `git` | `{branch, commit}` captured at open |
| `inputs` | Copied input file names, in copy order |
| `roles` | Seat map: `worker` and `mentor`, plus the opening `role` |
| `definition_of_done` | From `--definition` or the brief's `DEFINITION OF DONE` |
| `mentor` | `{goal, rules, ask, failure}` from flags or the brief |
| `task_text` | From `--task-text` or the brief's `TASK` (optional) |
| `interface_contract` | From `--interface` or the design's `INTERFACE CONTRACT` |
| `files` | From `--files` or the design's `FILES` |
| `design_input` | File name of the copied design, when given |

Each `roles[seat]` entry is `{session, loaded, cursor}`. `session` is the bound
session id (null until bound), `loaded` records whether the seat has done a full
`team_context`, and `cursor` is how far that seat has watched the journal.

### `input/`

`team open --brief`, `--feature`, and `--design` copy each given file verbatim;
when `--feature` is given, the parsed IR (`<artifacts_root>/<stem>.json`) is also
copied. The chunk payload delivered by `team_pull` renders these files inline.

### `journal.jsonl`

Append-only; every tool operation records itself. See
[TOOLS.md § Journal](TOOLS.md#journal).

### `output/`

Oracle attempt artifacts from `team_attempt`: `attempt-NN.txt` (full captured
output), `attempt-NN.diff` (git diff at that moment, when non-empty), and a
`.seq` counter. These are evidence, not journal entries.

## Lifecycle

```
team_open  ─ creates tasks/<date>/<task>/, task.json, 01-<role>/,
             copies inputs, appends journal line #1 (kind open)
worker     ─ team_pull (binds + delivers input pack)
             team_context (deterministic payload; appends advice)
             team_journal readback/plan/result/note
             team_attempt (writes output/, appends attempt)
             team_send ask (appends stuck)
mentor     ─ team_pull (the ask), team_context (mentor payload),
             team_send brief, team_done
worker     ─ green, forward mail handoff, team_done
team_close ─ --preserve moves the task whole to done/; otherwise deletes exactly
             that task and prunes an emptied date folder (or nested task parent)
```

## Concurrency And Locking

- `mailbox.py` locks per role (`role-<role>`) and once around `send`.
- `team.py` locks per task (`task-<task>`, hashed) for every mutation.
- Email/mailbox state is owned exclusively by the tools; never edit files under
  `state_root/mail/` or `state_root/tasks/` by hand.
- `harness clean state` guards against cleaning while items are in process.

## Known Limitations

These are real, current behaviors to be aware of (candidates for the backlog).
The four M10 limitations are resolved: the dead `sealed` field and guards, the
midnight `bind`/`close` date boundary, the `harness clean state` in-process
check, and the TS `findConfig` walk-up/fallback gap (see the
`task_state_layout`, `harness_cli`, and `ts_wiring` features).

- **`--ready` lists a phantom opening-role seat.** Accepted: `task.json` carries
  the opening role in `roles` beside `worker`/`mentor`, so `status --ready` also
  prints e.g. `READY: cart refactorer SPAWN_PENDING`. That seat is never pulled
  (resolution is by session) and the autobind plugin filters to
  `worker`/`mentor`, so it is cosmetic; a future schema could keep `role` out of
  the seat map. (Nested phase chunks were themselves invisible to `status
  --ready` until M9 made `task_docs` recursive; see
  [M9-VALIDATION.md](M9-VALIDATION.md).)

- **Session resolution skips a corrupt `task.json`.** Accepted:
  `find_task_for_session` scans every live task record to find the caller's
  binding; a corrupt record cannot be attributed to a session, and failing the
  whole scan on one bad file would break unrelated sessions, so it is skipped and
  the caller reports an unbound session. The name-resolved paths (`bind`/`close`)
  are the fail-closed ones: `load_task_json` refuses a corrupt record naming
  `corrupt` (see `team_recovery` 4). A future schema could keep a session index
  beside `task.json` so the corrupt record can be reported by name.
