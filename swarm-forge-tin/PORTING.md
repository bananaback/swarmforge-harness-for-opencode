# Porting The Pack To A Project — Agent Runbook

**Audience:** an opencode agent acting for the operator. The operator points you
at this file when the pack has been copied next to a new project, and expects
you to repoint the harness yourself — no manual edits by the operator.

**Goal:** make `swarm-forge-tin/harness.json` resolve to the target project, with
the operator's chosen persistent-test placement, and prove it with the harness
CLIs and the project's tests.

**One rule above all:** `harness.json` is the single source of truth. Every path
the tools and roles use comes from it. Never hardcode a path anywhere else.

---

## 0. TL;DR Agent Checklist

1. Ask the operator the five questions in §1 (project path, test placement,
   source root, test root, language). Do not guess.
2. Resolve the pack and project to **absolute** paths; decide the relative
   paths you will write (§2).
3. Edit `swarm-forge-tin/harness.json` (§3, §4). Keep `state_root`,
   `artifacts_root`, and `hot_tests` in the pack.
4. If the persistent root does not exist, create it from the template in §6.
5. Verify with `harness status` and `harness config` (§7).
6. Clean the shared areas before the first run (§7).
7. Run the project's unit/property tests and acceptance pipeline (§7).
8. Confirm no artifact, cache, or bytecode landed in the project tree (§8).
9. Report the resolved paths, the test results, and anything you could not
   resolve.

---

## 1. Ask The Operator First

Do not invent any of these. Use the `question` tool.

| Question | Why it matters | Default if the operator says "you decide" |
|---|---|---|
| What is the **target project directory**? | It becomes `workspace_root`. | A sibling of the pack. |
| Should the **persistent tests live in the pack or in the project**? | It sets `persistent_tests[].root` and `features`. | In the pack (keeps the project tree test-free). |
| What is the **source root** (where the project's code lives)? | It becomes `source_roots`; quality tools scan it. | `<project>/src`. |
| Where are the project's **existing tests/features**, if any? | You may reuse them instead of scaffolding new ones. | None — scaffold under the chosen root. |
| What **language/test runner** is the project? | The templates in §6 assume Python/pytest. | The pack's default (Python). |

If the project has no test root yet, you will create one (§6). If it already has
one, point `persistent_tests[].root` at it instead.

---

## 2. Path Resolution Rules (read this before editing)

These rules are implemented by `swarm-forge-tin/tools/wiring.py` and mirrored by
`.opencode/lib/wiring.ts`. Getting them wrong is the only way to break the port.

- **Base directory.** Every path in `harness.json` is resolved relative to the
  **directory that contains `harness.json`** — the pack root. `~` expands to the
  home directory. Absolute paths are used as-is. Every result is canonicalized.
- **Exception — `pythonpath`.** Each `persistent_tests[].pythonpath` entry is
  resolved relative to **that entry's own `root`**, not the pack.
- **The pack.** The pack is the config's directory when it contains
  `tools/wiring.py`; otherwise the built-in pack. `SWARM_PACK` overrides it.
- **`kind` selects the root.** A config that lives **inside the pack** prefers
  the `harness`-kind root, then the `project`-kind root. A config that lives
  **outside the pack** prefers `project`, then `harness`. So a wired-project
  config should mark its root `"kind": "project"`.
- **Environment overrides win over the file.** `SWARM_CONFIG` (which config
  file), `SWARM_PACK`, `SWARM_WORKSPACE`, `SWARM_STATE_ROOT`, `SWARM_HOT`. If
  resolution looks wrong, check for a stray `SWARM_*` variable first.
- **How the config is found** (when no `--config`/`SWARM_CONFIG`): walk up from
  the current directory looking for `harness.json` or
  `swarm-forge-tin/harness.json`; then `SWARM_PACK/harness.json`; then the
  built-in pack's `harness.json`; then `~/.config/swarm-forge/harness.json`.

**Keep the disposable areas in the pack.** Unless the operator explicitly wants
otherwise, leave these as the pack's shared areas so nothing lands in the
project:

| Field | Keep it at | Meaning |
|---|---|---|
| `state_root` | `".swarmforge"` (pack) | mail + team durable state |
| `artifacts_root` | `"dump"` (pack) | parse IR, dry reports, coverage, caches |
| `hot_tests` | `"hot_tests"` (pack) | generated acceptance entry points |

---

## 3. The Field Reference

| Field | Required | Resolved relative to | Notes |
|---|---|---|---|
| `version` | yes | — | Always `1`. |
| `workspace_root` | yes | config dir | The project under work. |
| `state_root` | recommended | config dir | Default: `<workspace>/swarm-forge-tin/.swarmforge`. |
| `artifacts_root` | recommended | config dir | Default: `<pack>/dump`. |
| `hot_tests` | recommended | config dir | Default: `<pack>/hot_tests`. |
| `persistent_tests` | yes | config dir | List of `{root, pythonpath, kind}`. |
| `source_roots` | yes | config dir | List of source trees; default `["src"]`. |
| `features` | recommended | config dir | The authored `.feature` root. |
| `roles` | no | — | The eight pipeline roles; keep as-is. |

`persistent_tests[]` entry:

| Key | Meaning |
|---|---|
| `root` | The persistent test root (contains `unit/`, `property/`, `features/`, `acceptance/`). |
| `pythonpath` | Import paths for the tests, each relative to `root`. Point at the project root so tests can import its source. |
| `kind` | `"project"` for a wired project (also `"harness"` for the pack's own tests). |

---

## 4. Choose The Placement, Then Edit

Decide with the operator, then write one of the two shapes below. In both, only
`workspace_root`, `source_roots`, `persistent_tests`, and `features` change;
the shared areas stay in the pack.

### Option A — persistent tests in the pack (recommended; project stays test-free)

```json
{
  "version": 1,
  "workspace_root": "../myproject",
  "state_root": ".swarmforge",
  "artifacts_root": "dump",
  "hot_tests": "hot_tests",
  "persistent_tests": [
    {
      "root": "project_tests/persistent",
      "pythonpath": ["../../../myproject"],
      "kind": "project"
    }
  ],
  "source_roots": ["../myproject/src"],
  "features": "project_tests/persistent/features",
  "roles": [
    "orchestrator", "specifier", "designer", "task-breaker",
    "coder", "refactorer", "architect", "mentor"
  ]
}
```

Path math (layout: `work/myproject/`, `work/swarm-forge-tin/`):

- config dir = `work/swarm-forge-tin`
- `workspace_root` = `../myproject` → `work/myproject`
- `root` = `project_tests/persistent` → `work/swarm-forge-tin/project_tests/persistent`
- `pythonpath` `../../../myproject` from `root` → `work/myproject` (persistent →
  project_tests → swarm-forge-tin → `work`, then `myproject`)

### Option B — persistent tests inside the project

```json
{
  "version": 1,
  "workspace_root": "../myproject",
  "state_root": ".swarmforge",
  "artifacts_root": "dump",
  "hot_tests": "hot_tests",
  "persistent_tests": [
    {
      "root": "../myproject/tests/persistent",
      "pythonpath": ["../.."],
      "kind": "project"
    }
  ],
  "source_roots": ["../myproject/src"],
  "features": "../myproject/tests/persistent/features",
  "roles": [
    "orchestrator", "specifier", "designer", "task-breaker",
    "coder", "refactorer", "architect", "mentor"
  ]
}
```

Path math:

- `root` = `../myproject/tests/persistent` → `work/myproject/tests/persistent`
- `pythonpath` `../..` from `root` → `work/myproject`

> In Option B the authored tests intentionally live in the project. The
> **disposable** areas still do not: `hot_tests/`, `dump/`, and `.swarmforge/`
> stay in the pack, and the project-side pytest root must keep its caches in the
> pack (§6).

### Switching without editing (optional)

If the operator wants two targets kept side by side, leave `harness.json` alone
and add a second config in the pack (e.g. `harness.myproject.json`). Select it
with `--config` or `SWARM_CONFIG`:

```bash
swarm-forge-tin/tools/harness --config swarm-forge-tin/harness.myproject.json status
SWARM_CONFIG=swarm-forge-tin/harness.myproject.json python3 swarm-forge-tin/tools/team.py --root . status
```

---

## 5. If The Operator Gives An Absolute Project Path

Relative paths are preferred (they survive moving the whole tree), but absolute
paths are valid. When the project is not a sibling of the pack, either use the
absolute path directly:

```json
"workspace_root": "/srv/apps/myproject",
"source_roots": ["/srv/apps/myproject/src"],
"persistent_tests": [
  { "root": "/srv/apps/myproject/tests/persistent", "pythonpath": [".."], "kind": "project" }
],
"features": "/srv/apps/myproject/tests/persistent/features"
```

…or keep the test root in the pack with an absolute `pythonpath` back to the
project. Never mix a relative `root` with an absolute `pythonpath` unless you
have verified the resolved result with `harness config`.

---

## 6. Create The Persistent Test Root (only if it is missing)

A persistent root is a pytest root: it needs a `pytest.ini` and a `conftest.py`.
Copy the pack's working example and adapt it:

- `swarm-forge-tin/project_tests/pytest.ini`
- `swarm-forge-tin/project_tests/conftest.py`

Directory layout to create under the chosen `root`:

```
<persistent root>/
├── pytest.ini
├── conftest.py
├── unit/          # TDD unit tests
├── property/      # hypothesis properties
├── features/      # authored Gherkin specs
└── acceptance/    # step handlers + runtime + generator + runner
```

**`pytest.ini` — the two lines that matter for a project-side root:**

```ini
[pytest]
testpaths = unit
pythonpath = ../..
cache_dir = <pack>/dump/pytest_cache-<project>
```

Replace `<pack>` and `<project>`. Do not add inline `;` comments to these lines —
`pytest.ini` does not parse them and they become part of the value.

- `pythonpath` must reach the project root so tests can `import src.<mod>`
  (relative to this file's directory).
- `cache_dir` must point into the pack's `dump/`, never the project. It is
  mandatory for Option B: without it pytest writes `.pytest_cache/` into the
  project tree — a leak.

**`conftest.py` — keep bytecode and hypothesis state out of the project:**

```python
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_dump_dir = Path("<pack>") / "dump"
os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(_dump_dir / "hypothesis-<project>"))
```

Resolve `<pack>` and `<project>` to real paths (relative or absolute). For
Option A, the pack's existing `project_tests/conftest.py` already does this.

For the acceptance pipeline, reuse the pack's runner and generator:
`swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py` and
`generator.py`. They read the features root and write generated entry points to
the configured `hot_tests`, never to the project.

---

## 7. Verify (do this before reporting done)

Run these from the workspace root, in order.

```bash
# 1. Every path resolves and exists (exit 2 on a bad config)
swarm-forge-tin/tools/harness status

# 2. The resolved JSON, to check the persistent root and pythonpath
swarm-forge-tin/tools/harness config

# 3. Clean the shared areas before the first run of a new project
swarm-forge-tin/tools/harness clean all

# 4. The project's unit + property tests (from the chosen persistent root)
cd <persistent root> && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# 5. The project's acceptance pipeline (parse -> dry -> generate -> run)
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.json
```

Expected: `harness status` marks every row `[ok]`; the tests pass; the acceptance
pipeline exits 0. If the project has no tests yet, say so and report the
resolved paths instead of inventing tests.

---

## 8. Leak Check (the operator cares about this)

After running, confirm the project tree gained nothing disposable:

```bash
find <project dir> \( -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .hypothesis -o -name .coverage \) -print
```

An empty result is the pass condition. If anything appears, the cause is one of:
a missing `PYTHONDONTWRITEBYTECODE=1`, a `cache_dir` that points into the
project, or a `conftest.py` that does not set `sys.dont_write_bytecode`. Fix the
setup, delete the stray files, and re-run.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `harness: cannot read config ...` | Bad path or malformed JSON | Fix `harness.json`; the error names the file. |
| A path resolves to the wrong place | A stray `SWARM_*` env var overrides the file | Unset `SWARM_CONFIG` / `SWARM_PACK` / `SWARM_WORKSPACE` / `SWARM_STATE_ROOT` / `SWARM_HOT`. |
| Wrong persistent root selected | The config's location picks the preferred `kind` | Mark the project root `"kind": "project"`; check `harness config`. |
| Tests cannot import the project | `pythonpath` is wrong | Remember it is relative to `root`, not the pack. |
| Generated tests collide across projects | The shared `hot_tests/` holds the previous project's entry points | `harness clean hot` (or `all`) before switching. |
| `clean state` refuses | Mail/team items are in process | Only use `--force` with operator confirmation. |
| `.pytest_cache`/`__pycache__` in the project | Missing cache/bytecode guards | See §6 and §8. |
| `run_acceptance: pass --config` | The runner needs the config explicitly | Pass `--config swarm-forge-tin/harness.json` or set `SWARM_CONFIG`. |

---

## 10. Agent Rules And Boundaries

- Edit **only** `harness.json` (or add a new config in the pack). Do not edit the
  tools, the agent prompts, or the constitution to make a path work.
- Never write into the project's source roots. The project source stays
  test-free; only Option B's persistent root is authored inside the project.
- Never delete `swarm-forge-tin/harness_tests/persistent/` (the pack's own
  tests). `hot_tests/`, `dump/`, and `.swarmforge/` are disposable; the project
  tree is not.
- Never create, read, edit, or move files under `<state_root>/mail/` or
  `<state_root>/tasks/`; the `mail_*`/`team_*` tools own that state.
- Prefer relative paths; they survive moving the pack and project together.
- After editing, always run `harness status` **and** `harness config` and read
  the resolved output before claiming the port is done.
- Report back: the config file you changed, the resolved `workspace_root` and
  persistent root, the placement chosen, and the test results.

---

## 11. Worked Example — Repointing From The Pack's Own Project To A New One

Before (self-hosting, the pack points at its own repo):

```json
"workspace_root": "..",
"source_roots": ["tools"],
"persistent_tests": [
  { "root": "harness_tests/persistent", "pythonpath": ["."], "kind": "harness" },
  { "root": "project_tests/persistent", "pythonpath": ["."], "kind": "project" }
],
"features": "harness_tests/persistent/features"
```

After (Option A, tests in the pack, pointing at `myproject`):

```json
"workspace_root": "../myproject",
"source_roots": ["../myproject/src"],
"persistent_tests": [
  { "root": "project_tests/persistent", "pythonpath": ["../../../myproject"], "kind": "project" }
],
"features": "project_tests/persistent/features"
```

To go back, restore the four "Before" lines and run `harness clean all`. That is
the entire switch: four fields in one file.
