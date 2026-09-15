# Tools

How the harness is operated. Two Python CLIs own all durable work —

- **`mailbox.py`** — durable inter-role mail (the task chain between roles).
- **`team.py`** — per-task chunks: seat binding, journaling, oracle attempts, and
  deterministic context payloads.

— and a small set of opencode bridges expose them to the agents. Storage layout
and wiring are in [ARCHITECTURE.md](ARCHITECTURE.md); when each role calls what
is in [WORKFLOW.md](WORKFLOW.md).

## Conventions

- Every CLI takes `--root <workspace>` (default: CWD) and `--state-root <path>`
  (default: from wiring). `--json` switches output to a JSON object.
- Tools resolve the workspace's state root from `harness.json`; never hand-edit
  files under `<state_root>/mail/` or `<state_root>/tasks/`.
- A wake line carries no task. The recipient pulls the durable record.
- Exit 2 means a validation or refusal error, printed as `MAIL ERROR:` or
  `TEAM ERROR:` with a `- problem` line per problem.

## Mail Tool (`mailbox.py`)

Durable mail is the task chain: a sender leaves a message, the orchestrator
dispatches the role, and the role pulls only its own mailbox. One in-process item
per role, owned by the session that claimed it.

### Storage

```
<state_root>/mail/
  inbox/<role>/{new,in_process,completed,failed}/
  counters/seq
  locks/
```

A message document carries: `id`, `from`, `to` (all recipients), `recipient`,
`priority` (two digits), `type` (`handoff` | `note`), `task`, `message`,
`content_hash`, `created_at`/`enqueued_at`/`dequeued_at`/`completed_at`,
`sender_session`, `owner_session`, `batch_id`, `result`, and a rendered
`payload`.

### Message Types

| Type | Requires | Message | Payload |
|---|---|---|---|
| `handoff` | `task` name | optional, ≤ 300 chars, one line | `handoff for task: <task>` + blank line + message |
| `note` | — | required, ≤ 80 chars, one line | the message |

`task` must be ≤ 80 chars, start alphanumeric, and use letters/digits/`.`/`_`/`-`
separated by `/`. `note` mail is only used when the user or a role prompt
explicitly directs it.

### Operations

| Command | Effect |
|---|---|
| `send --from R --to A[,B] [--type handoff\|note] [--priority NN] [--task T] [--message M] [--session S]` | Queue to recipients; dedups identical live content as `DUPLICATE` |
| `pull --as R [--mode task\|batch] [--session S] [--takeover]` | Resume or claim the role's item |
| `done --as R [--id ID] [--result TEXT] [--session S]` | Complete in-process mail; prints `MAIL_WAITING` or `NO_TASK` |
| `status [--role R] [--session S]` | Per-role queued/in-process/completed counts and holders |

Details:

- **send** validates sender (lowercase role, or builtin `build`/`plan`),
  recipients (known roles, no repeats), priority (`00`–`99`), type, message
  length/one-line, and task. It hashes `(from, type, task, message)`; if an
  identical item is in `new` or `in_process` for a recipient, it reports
  `DUPLICATE` and does not enqueue a second copy.
- **pull** resumes an in-process item first (more than one is ambiguous and
  refused); otherwise claims the top-priority `new` item. `--mode batch` claims
  all queued mail at the top priority as one unit (`batch_id`). Ownership: an
  item owned by another session is refused unless `--takeover`, which is
  operator-confirmed only.
- **done** completes all in-process items, or just `--id`. It records
  `completed_at`/`result` and moves them to `completed/`. It refuses mixed or
  foreign ownership.
- **status** discovers roles from the configured `roles`, `.opencode/agents/*.md`,
  and existing inbox dirs.

## Team Tool (`team.py`)

Routes work by `(task, seat)` and never lets a model handle a session id. State
is the dated task/chunk layout from [ARCHITECTURE.md](ARCHITECTURE.md#state-layout).

### Seats, Roles, Edges

- **Seats**: `worker`, `mentor`.
- **Roles** (validation): `orchestrator`, `specifier`, `coder`, `refactorer`,
  `architect`, `mentor`.
- **Edges** are fixed and tool-enforced:

  | Edge | Allowed kind |
  |---|---|
  | worker → mentor | `ask` |
  | mentor → worker | `brief` |

Models name only the target seat; the task and seat come from the caller's
session binding.

### Operations

| Command | Caller | Effect |
|---|---|---|
| `open <task> --role R [--brief F] [--feature F] [--design F] [--definition S] [--task-text S] [--interface S] [--files S] [--goal S] [--rules S] [--ask S] [--failure S]` | orchestrator | Create the dated task folder, chunk `01-<role>`, inputs, `task.json`, and the `open` journal line |
| `bind <task> --seat S --session ID [--takeover]` | orchestrator | Atomic seat binding; refused if bound unless `--takeover`; resets `loaded`/`cursor` |
| `status [--ready]` | anyone | Read-only task/seat report; `--ready` lists spawnable seats |
| `close <task> [--preserve]` | orchestrator | Delete the task, or move it whole to `done/` |
| `pull --session ID [--seat HINT]` | seat | Claim/resume the chunk item; binds on first pull |
| `send --to SEAT --kind K --message M --session ID` | seat | Enqueue an ask/brief in the caller's chunk |
| `done --session ID [--result S]` | seat | Append the `done` line; prints `COMPLETED` then `NO_TASK` |
| `context --session ID [--delta]` | seat | Deliver the chunk payload / journal (see below) |
| `journal --kind K --entry JSON\|@FILE [--attempt N] --session ID` | worker | Append one journal entry |
| `attempt --command C [--cwd D] [--timeout SEC] --session ID` | worker | Run the oracle and record an attempt artifact |

Details:

- **open** copies `brief`/`feature`/`design` into `input/`; when `feature` is
  given, the parsed IR `<artifacts_root>/<stem>.json` is copied too. Section
  fields are taken from the flags first, then extracted from the brief/design
  text (`DEFINITION OF DONE`, `TASK`, `INTERFACE CONTRACT`, `FILES`, and mentor
  `GOAL`/`RULES`/`ASK`/`FAILURE`). It captures `git {branch, commit}` and writes
  journal line #1 (`open`).
- **bind** refuses a session already serving another seat, and refuses a bound
  seat unless rebinding to the same session or `--takeover`.
- **status** prints `TASK` / `SEALED` / `SEAT session ... loaded ... cursor ...`
  per task. `--ready` prints one line per unsealed seat:
  `READY: <task> <seat> <SPAWN_PENDING|queued>` — `SPAWN_PENDING` when the seat
  has no session, `queued` when it does.
- **close** with `--preserve` moves the task to `done/<date>/<task>`; without it,
  deletes exactly that task and prunes an emptied date folder (and any emptied
  nested parent).
- **pull** resolves the caller by session. If the session is already bound to the
  seat, it prints `RESUMED: yes` plus the input pack; otherwise it binds and
  prints the input pack. An unbound session is a hard error:
  `session is not bound to any team seat ...`.
- **send** validates the edge and kind. An `ask` appends a `stuck` journal entry;
  a `brief` is dialogue and is not journaled (it lives in session turns).
- **done** appends a `done` entry and always prints `NO_TASK` (team completion is
  not tied to the mail queue).

### Journal

Append-only, one JSON object per line. Every entry has `seq`, `kind`, and `at`.

| Kind | Written by | Carries |
|---|---|---|
| `open` | `team_open` | git branch/commit, copied inputs |
| `readback` | worker (`team_journal`) | goal/constraints/done understanding |
| `plan` | worker | decision record before a distinct approach |
| `result` | worker (`--attempt N` attaches attempt facts) | evidence and reading after an oracle run |
| `note` | worker | lessons that survive the chunk |
| `attempt` | `team_attempt` | cmd, cwd, exit, duration, timeout, refs |
| `stuck` | `team_send --kind ask` | from/to, the ask message |
| `advice` | `team_context` | delivery mode and count, seat cursor advance |
| `done` | `team_done` | optional result digest |

Worker kinds (`readback`, `plan`, `result`, `note`) may only be written by the
`worker` seat. `team_journal --attempt N` merges the fields of attempt `N` into
the entry (the entry keeps its own kind/seq); an unknown attempt number is
refused. See [examples/worker-journal.md](examples/worker-journal.md).

### Attempts

`team_attempt` runs the command with `shell=True` in `cwd` (default the
workspace root) and records:

- `output/attempt-NN.txt` — combined stdout+stderr.
- `output/attempt-NN.diff` — `git diff` at that moment, when non-empty.
- `output/.seq` — the attempt counter.
- a journal `attempt` line with `cmd`, `cwd`, `exit`, `duration_s`, `timeout`,
  `refs`.

A timeout (optional `--timeout`) kills the oracle's whole process group and
records exit `124`. It prints `ATTEMPT: N`, `EXIT:`, `CWD:`, then the output.

### Context Delivery

`team_context` renders one of three payloads, then appends an `advice` entry and
advances the seat's cursor:

| Condition | Payload |
|---|---|
| full call, worker seat, task role `coder` | 11-section coder payload |
| full call, mentor seat | system prompt + 5-section mentor payload |
| anything else | input pack + `JOURNAL:` + journal entries |

`--delta` requires a prior full load (`loaded`), else `LOAD_REQUIRED`; it returns
journal entries since the seat's cursor. Dialogue (ask/brief) is never delivered
by context — it lives in the advisor's session turns.

> The coder payload applies only to a coder task's worker seat. A
> refactorer/architect chunk's worker gets the generic input+journal payload.

## Context Payload Contracts

### Coder Payload (11 sections, fixed order)

Assembled only from `task.json` and the resolved config — no path discovery.

| # | Section | Source |
|---|---|---|
| 1 | `TASK` | task name + `task_text` |
| 2 | `DEFINITION OF DONE` | `definition_of_done` |
| 3 | `RESOLVED PATHS` | workspace / state / artifacts / hot / persistent-test root |
| 4 | `INPUTS` | copied input names |
| 5 | `FEATURE` | first `.feature` in `input/`, verbatim |
| 6 | `INTERFACE CONTRACT` | design input file, else `interface_contract` |
| 7 | `FILES` | `files`, else the design input |
| 8 | `HOW TO RUN` | three templated commands (below) |
| 9 | `PRIOR ATTEMPT` | each `output/attempt-*.txt`, or `no prior attempt` |
| 10 | `WHEN STUCK` | fixed policy (below) |
| 11 | `WHEN DONE` | fixed policy (below) |

`HOW TO RUN` template:

```
persistent: cd {persistent} && PYTHONDONTWRITEBYTECODE=1 {python} -m pytest
acceptance: {python} {acceptance}/run_acceptance.py
lint: {pack}/tools/ruff4py {source} {persistent}
```

`WHEN STUCK` (no caps):

```
No attempt cap: keep the oracle loop running while progress is real.
When the next change would be a guess, ask one question with the exact command, output, and file:line.
Ask again after each brief; the pair keep talking until the path is clear.
Never ask 'is my code correct'; the oracle answers that.
Interface, scope, or dependency doubt: ask before guessing.
```

`WHEN DONE`:

```
Journal a RESULT digest and keep the mail pointer <= 300 characters.
Hand off to refactorer with the digest pointer.
Leave the tree dirty; do not commit.
```

### Mentor Payload (system prompt + 5 sections)

Assembled from `task.json` and the journal, with no model call. Line 1 is the
fixed system prompt:

```
You are the mentor seat. Advise from the task and chunk state below;
answer the worker's ask with the failure evidence in view.
```

| Section | Source (first non-empty wins) |
|---|---|
| `GOAL` | `mentor.goal` (flag or brief `GOAL`) |
| `RULES` | `mentor.rules` |
| `TRAIL` | worker-kind journal entries in `seq` order, or `no trail` |
| `ASK` | `mentor.ask`, else the latest `stuck` message, else `no ask` |
| `FAILURE` | `mentor.failure`, else the latest `stuck` failure/evidence, else its first ref file, else `no failure` |

The payload is computed before the `advice` entry is appended and
`TRAIL` includes only worker kinds, so repeated full calls yield the same
payload. See [examples/mentor-payload.md](examples/mentor-payload.md).

## opencode Bridges

The bridges are thin: they resolve wiring and spawn the Python CLI.

| Bridge | Tools | Invocation |
|---|---|---|
| `.opencode/tools/mail.ts` | `mail_send`, `mail_pull`, `mail_done`, `mail_status` | `python3 <pack>/tools/mailbox.py --root <workspace> --from <agent> --session <id> ...` |
| `.opencode/tools/team.ts` | `team_open`, `team_bind`, `team_status`, `team_close`, `team_pull`, `team_send`, `team_done`, `team_context`, `team_journal`, `team_attempt` | `python3 <pack>/tools/team.py --root <workspace> --session <id> ...` |

- `.opencode/lib/wiring.ts` mirrors the Python resolver (`findConfig`,
  `findPack`, `loadWiring`) for the bridges.
- `.opencode/lib/team-autobind.ts` holds the pure auto-bind core:
  `seatForAgent` maps `coder`/`refactorer`/`architect` → `worker` and `mentor` →
  `mentor`; `parseReady` reads `READY:` lines; `autoBindPendingSeat` finds the
  project root, reads `status --ready`, and binds the single matching
  `SPAWN_PENDING` seat (refusing when there is none or more than one).
- `.opencode/plugins/team-autobind.ts` wires the core to the `chat.message` hook:
  on any message containing `TEAM_WAITING`, it auto-binds the spawned session
  before the child's first tool call. `team_bind` remains the manual fallback.

## Wake Contract

Constant lines, zero payload:

```
MAIL_WAITING: run mail_pull    # mail dispatch
TEAM_WAITING: run team_pull    # bound team seat
```

All content comes from the subsequent pull/context. Content in a wake line would
create a second source of truth, so it is rejected by design.
