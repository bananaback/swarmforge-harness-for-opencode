# Underlying State Design

Live work is grouped by task open date; each task is one self-contained folder; each chunk is one role's turn.

## Layout

```text
<state_root>/
  mail/                                    # handoffs between roles; not task state
  tasks/                                   # live work, newest date last
    2026-09-14/                            # date folder = task open day (UTC), sortable
      feature/
        periods/                           # task: feature/periods
          task.json                        # WHO: orchestrator, first tool call team_open.
                                           #   task name, branch, feature file, chunk order,
                                           #   RESOLVED PATHS (resolved from harness.json)
          01-coder/                        # chunk: <NN>-<role>, order set by orchestrator
            input/                         # copies of what the coder is given; write once
              brief.md                     # WHO: orchestrator calls team_open --brief <file>.
                                           #   TASK (mission, branch, do-not-commit)
              periods.feature              # WHO: orchestrator calls team_open --feature <file>.
                                           #   FEATURE (verbatim)
              periods.json                 # WHO: team_open copies the specifier's parsed IR.
                                           #   INPUTS
              design.md                    # WHO: orchestrator calls team_open --design <file>.
                                           #   INTERFACE CONTRACT + FILES (allowlist, call sites)
            journal.jsonl                  # WHO: only tools append; one line per entry
              # n=1   open     WHO: team_open (orchestrator)
              #                 -> CURRENT STATE: git branch/commit, baseline result,
              #                    input file list, bound session
              # n=2   readback WHO: team_journal (coder) -> goal/done understanding
              # n=10  plan     WHO: team_journal (coder) -> hypothesis, decision, expected outcome
              # n=12  attempt  WHO: team_attempt (tool, from coder's params)
              #                 -> cmd, exit, failure signature, files: attempt-01.txt/.diff
              # n=44  stuck    WHO: team_send --kind ask (coder) -> tried, command, file:line
              # n=51  advice   WHO: team_context delivery (tool) -> mentor ruling
              # n=62  done     WHO: team_done (coder) -> RESULT digest
            output/
              attempt-01.txt               # WHO: team_attempt (tool) -> captured oracle output
              attempt-01.diff              # WHO: team_attempt (tool) -> diff at that attempt
          02-refactorer/                   # same three parts: input/ · journal.jsonl · output/
          03-architect/                    # same
      bug/
        leap-year-crash/                   # task: bug/leap-year-crash, opened the same day
    2026-09-15/
      feature/
        invoice-truncate/
  done/                                    # preserved tasks, mirrored date layout
    2026-09-14/
      feature/periods/                     # moved here whole by team_close --preserve
        01-coder/ · 02-refactorer/ · 03-architect/
```

## Who writes each file

| File | Written by | Feeds context section |
|---|---|---|
| `task.json` | orchestrator via `team_open` | DEFINITION OF DONE, RESOLVED PATHS, INPUTS, HOW TO RUN |
| `input/brief.md` | orchestrator via `team_open --brief` | TASK |
| `input/<feature>.feature` | orchestrator via `team_open --feature` | FEATURE |
| `input/<feature>.json` (IR) | `team_open` copies the specifier's parsed IR | INPUTS |
| `input/design.md` | orchestrator via `team_open --design` | INTERFACE CONTRACT, FILES |
| `journal.jsonl` | tools only, one line per entry | CURRENT STATE, PRIOR ATTEMPT, WHEN DONE, UPDATES |
| `output/attempt-NN.txt` | `team_attempt` | PRIOR ATTEMPT (evidence) |
| `output/attempt-NN.diff` | `team_attempt` | PRIOR ATTEMPT (evidence) |

## Who writes each journal line

| n | kind | Written by | Feeds context section |
|---|---|---|---|
| 1 | `open` | `team_open` (orchestrator) | CURRENT STATE (git branch/commit, baseline result, input file list, bound session) |
| — | `readback` | `team_journal` (coder) | coder understanding of goal/done |
| — | `plan` | `team_journal` (coder) | hypothesis, decision, expected outcome |
| — | `attempt` | `team_attempt` (tool, from coder's params) | cmd, exit, failure signature, file refs |
| — | `stuck` | `team_send --kind ask` (coder) | what was tried, exact command, file:line |
| — | `advice` | `team_context` delivery (tool) | mentor ruling |
| — | `done` | `team_done` (coder) | RESULT digest |

## Not stored (fixed templates, filled by the context tool at pull time)

- DEFINITION OF DONE — template + values from `task.json` and the `open` line.
- ACCEPTANCE DELIVERY — template, same for every coder chunk.
- HOW TO RUN — template + paths read from `task.json`.
- WHEN STUCK / BUDGET — template + attempt count read from `journal.jsonl`.
- UPDATES — journal lines appended during the session; nothing extra stored.

## Lifecycle

1. `team_open` — creates `tasks/<date>/<task>/`, writes `task.json`, makes `01-coder/`, copies the given files into `input/`, appends the `open` line with git state and baseline.
2. Coder works — tools append `readback/plan/attempt/stuck/done` lines and write attempt outputs to `output/`.
3. Mentor replies — the delivery tool appends the `advice` line; `mail/` stays transport only.
4. `team_close` — writes `dump/tasks/<task>.json`, then deletes `tasks/<date>/<task>/` or moves it to `done/<date>/<task>/` with `--preserve`. Removing an emptied date folder is part of the same call.

## Rules

- A task folder contains only `task.json` and `NN-role/` chunk folders.
- A chunk folder contains only `input/`, `journal.jsonl`, and `output/`.
- `input/` is write-once; `journal.jsonl` only grows; nothing in the folder is rewritten by hand.
- Preserving one task never touches another; deleting one cleans exactly it.
- `done/` mirrors `tasks/`, so a later DB import can walk both with the same rules.
