# Feature Coverage Map

Requirement -> feature traceability for the M12 gate ("Gherkin features as the
single source of truth"). Every documented harness command, refusal, invariant,
context payload, recovery path, and pipeline seam is listed here with the
feature that specifies it. A requirement with no scenario is a **gap** and is
visible on purpose.

Status values:

- **covered** - an existing committed feature already specifies it.
- **new** - specified in an increment and handed to the coder.
- **gap** - documented but not yet specified; queued for a later increment.

Feature files live under `<pack>/harness_tests/persistent/features/`. Scenario
names carry the feature name and a stable index, so a row below can cite
`<feature> <n>`.

## Mail tool (`mailbox.py`)

Source: [TOOLS.md § Mail Tool](TOOLS.md#mail-tool-mailboxpy).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| MAIL-SEND-QUEUE | `send` queues one item per named recipient | `mail_queue` 1 | new |
| MAIL-SEND-PAYLOAD | a handoff payload names the task and carries the message | `mail_queue` 2 | new |
| MAIL-NOTE-PAYLOAD | a note payload is the message alone | `mail_queue` 3 | new |
| MAIL-SEND-DEDUP | identical live content reports `DUPLICATE` and does not enqueue | `mail_queue` 4 | new |
| MAIL-PULL-PRIORITY | `pull` claims the top-priority queued item | `mail_queue` 5 | new |
| MAIL-PULL-RESUME | `pull` resumes an in-process item before claiming new mail | `mail_queue` 6 | new |
| MAIL-PULL-BATCH | `--mode batch` claims all top-priority queued items as one unit | `mail_queue` 7 | new |
| MAIL-DONE-COMPLETE | `done` completes the item, records the result, moves it to `completed` | `mail_queue` 8 | new |
| MAIL-DONE-SIGNAL | `done` prints `MAIL_WAITING` or `NO_TASK` | `mail_queue` 8, 9 | new |
| MAIL-STATUS-COUNTS | `status` reports queued and in-process counts | `mail_queue` 10 | new |
| MAIL-STATUS-ROLES | `status` discovers the known roles | `mail_queue` 11 | new |
| MAIL-PULL-OWNER | a foreign session cannot resume a claimed item | `mail_queue` 12 | new |
| MAIL-PULL-TAKEOVER | `--takeover` reassigns ownership to another session | `mail_queue` 13 | new |
| MAIL-PULL-AMBIG | more than one in-process item is an ambiguous resume and is refused | `mail_queue` 14 | new |
| MAIL-SEND-VALIDATE | invalid sender/recipient/priority/task/type/message is refused with a problem | `mail_validation` 1-7 | new |
| MAIL-SEND-BUILTIN | builtin senders `build`/`plan` are accepted | `mail_validation` 8 | new |
| MAIL-ERROR-FORMAT | a refusal exits 2 and prints one `- problem` line per problem | `mail_validation` 1-7 (the full problem set) | new |
| MAIL-DONE-OWNER | `done` refuses a foreign owner and names the holder | `mail_queue` 15 | new |
| MAIL-DONE-ID | `done --id` completes only the named in-process item | `mail_queue` 16 | new |
| MAIL-STATUS-HOLDER | `status` reports the in-process holder session | `mail_queue` 17 | new |
| MAIL-DONE-NOITEM | `done` without an in-process item is refused and leaves the queue | `mail_recovery` 1 | new |
| MAIL-PULL-COMPLETED | a completed item is never re-claimed; the next pull takes the next queued | `mail_recovery` 2 | new |
| MAIL-SEND-RESEND | a re-send after completion is a new item and reports `QUEUED` | `mail_recovery` 3 | new |
| MAIL-PULL-CORRUPT | a corrupt queued item is refused naming `corrupt` and stays queued | `mail_recovery` 4 | new |
| MAIL-DONE-CORRUPT | a corrupt in-process item is refused naming `corrupt` and stays in process | `mail_recovery` 5 | new |

## Team tool (`team.py`)

Source: [TOOLS.md § Team Tool](TOOLS.md#team-tool-teampy).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| TEAM-OPEN-LAYOUT | `open` creates the dated task/chunk layout | `task_state_layout` 1 | covered |
| TEAM-OPEN-INPUTS | `open` copies brief/feature/design and the parsed IR | `task_state_layout` 2 | covered |
| TEAM-OPEN-JOURNAL | `open` writes journal line #1 with git state and inputs | `task_state_layout` 3 | covered |
| TEAM-JOURNAL-KINDS | worker journal kinds are accepted | `task_state_layout` 4 | covered |
| TEAM-JOURNAL-UNKNOWN | an unknown journal kind is refused, journal unchanged | `task_state_layout` 5 | covered |
| TEAM-OP-KINDS | tool operations record their journal kinds | `task_state_layout` 6 | covered |
| TEAM-INV-APPEND | the journal only grows, ordered by sequence | `task_state_layout` 7 | covered |
| TEAM-CLOSE-PRESERVE | `close --preserve` moves the task whole to `done/` | `task_state_layout` 8 | covered |
| TEAM-CLOSE-DELETE | `close` deletes exactly that task | `task_state_layout` 9 | covered |
| TEAM-CLOSE-PRUNE | `close` prunes an emptied date folder | `task_state_layout` 10 | covered |
| TEAM-CONTEXT-CODER | a coder worker gets the 11-section coder payload | `deterministic_coder_payload` 1-5 | covered |
| TEAM-CONTEXT-MENTOR | a mentor gets the system prompt + 5-section payload | `deterministic_mentor_payload` 1-7 | covered |
| TEAM-OPEN-SECTIONS | `open` extracts sections from flags, then brief/design | `team_open_sections` 1-6 | new |
| TEAM-BIND | `bind` is atomic and resets `loaded`/`cursor` | `team_seat_routing` 1, 2 | new |
| TEAM-BIND-REFUSE | `bind` refuses a bound seat unless it is a fresh session with `--takeover` | `team_seat_routing` 3 | new |
| TEAM-BIND-SESSION | `bind` refuses a session already serving another seat | `team_seat_routing` 4 | new |
| TEAM-STATUS | `status` prints task/seat/session/loaded/cursor | `team_seat_routing` 8, 9 | new |
| TEAM-STATUS-READY | `status --ready` lists spawnable seats | `team_seat_routing` 10, 11 | new |
| TEAM-PULL-SEAT-HINT | a pull seat hint must match the bound seat | `team_seat_routing` 7 | new |
| TEAM-PULL-RESUME | `pull` reports `RESUMED: yes` for a bound seat | `team_seat_routing` 5 | new |
| TEAM-PULL-UNBOUND | an unbound session is a hard error | `team_seat_routing` 6 | new |
| TEAM-SEND-EDGE | `send` validates the fixed worker/mentor edge and kind | `team_mentor_exchange` 3 | new |
| TEAM-SEND-ASK | an `ask` appends a `stuck` journal entry | `team_mentor_exchange` 1 | new |
| TEAM-SEND-BRIEF | a `brief` is dialogue and is not journaled | `team_mentor_exchange` 2 | new |
| TEAM-DONE | `done` appends a `done` entry and prints `NO_TASK` | `team_mentor_exchange` 4 | new |
| TEAM-CONTEXT-GENERIC | a non-coder worker gets the input + journal payload | `team_context_delivery` 1 | new |
| TEAM-CONTEXT-DELTA | `--delta` returns entries since the seat cursor | `team_context_delivery` 3 | new |
| TEAM-CONTEXT-LOAD | `--delta` before a full load is `LOAD_REQUIRED` | `team_context_delivery` 4 | new |
| TEAM-CONTEXT-ADVICE | `context` appends an `advice` entry and advances the cursor | `team_context_delivery` 2 | new |
| TEAM-CONTEXT-DIALOGUE | dialogue is never delivered by `context` | `team_context_delivery` 5 | new |
| TEAM-JOURNAL-ATTEMPT | `journal --attempt N` merges attempt facts; unknown N refused | `team_oracle_attempt` 6, 7 | new |
| TEAM-ATTEMPT-RUN | `attempt` runs the oracle and records output, diff, seq, journal | `team_oracle_attempt` 1-4 | new |
| TEAM-ATTEMPT-TIMEOUT | a timed-out attempt is killed and recorded as exit 124 | `team_oracle_attempt` 5 | new |
| TEAM-ATTEMPT-PRINT | `attempt` prints `ATTEMPT`, `EXIT`, `CWD`, then output | `team_oracle_attempt` 1 | new |
| TEAM-INV-WRITEONCE | `input/` is write-once | `team_input_write_once` 1-3 | new |
| TEAM-INV-NOSEAL | the task record carries no dead seal flag | `task_state_layout` 11 | new |
| TEAM-BIND-PREVDATE | `bind` finds a task filed under an earlier date | `task_state_layout` 12 | new |
| TEAM-CLOSE-PREVDATE | `close` finds a task filed under an earlier date | `task_state_layout` 13 | new |
| TEAM-VALID-ROLE | `open` refuses a role outside the documented list | `team_command_validation` 1 | new |
| TEAM-VALID-TASK | `open` refuses a task name with an empty leading segment | `team_command_validation` 2 | new |
| TEAM-VALID-SEAT | `bind` refuses a seat outside `worker`/`mentor` | `team_command_validation` 3 | new |
| TEAM-VALID-WORKER-KIND | only the worker seat may append worker journal kinds | `team_command_validation` 4 | new |
| TEAM-CONTEXT-PREVDATE | a session-resolved `context` finds a task filed under an earlier date | `team_recovery` 1 | new |
| TEAM-CONTEXT-IDENTITY | a coder worker's full payload carries its `CONTEXT: ...` identity line with `TASK` still first | `team_recovery` 1 | new |
| TEAM-DONE-PREVDATE | a session-resolved `done` finds a task filed under an earlier date | `team_recovery` 2 | new |
| TEAM-DONE-REPEAT | a repeated `done` appends a `done` entry and reports `NO_TASK` | `team_recovery` 3 | new |
| TEAM-BIND-CORRUPT | `bind` refuses a corrupt `task.json` naming `corrupt` | `team_recovery` 4 | new |

## Task-breaker bridge (`taskbreak.py`)

Source: [TOOLS.md § Task-Breaker Bridge](TOOLS.md#task-breaker-bridge-taskbreakpy).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| TB-PLAN-VALID | a valid plan opens one team task per chunk | `taskbreak_bridge` 1, 2 | new |
| TB-PLAN-FIELDS | the chunk's fields reach the opened task | `taskbreak_bridge` 3 | new |
| TB-PLAN-EMPTY | an empty chunk list is refused | `taskbreak_bridge` 4 | new |
| TB-PLAN-DUP | duplicate task names are refused | `taskbreak_bridge` 5 | new |
| TB-PLAN-ROLE | only `coder`/`refactorer`/`architect` roles are accepted | `taskbreak_bridge` 6 | new |
| TB-PLAN-INPUTS | each chunk needs `brief_text` or `brief`; design optional | `taskbreak_bridge` 7, 8 | new |
| TB-PLAN-MISSING | a referenced input file that does not exist is refused | `taskbreak_bridge` 9 | new |
| TB-PLAN-ATOMIC | validation is all-or-nothing; no chunk opens on any problem | `taskbreak_bridge` 7, 9 | new |
| TB-STAGE | staged brief/design land under `artifacts_root/taskbreak/` | `taskbreak_bridge` 10 | new |
| TB-ORACLE | `ORACLE` is appended to the brief when absent, kept once when present | `taskbreak_bridge` 10, 11 | new |
| TB-DRY | `--dry-run` stages without opening | `taskbreak_bridge` 12 | new |
| TB-JSON | `--json` prints the opened task names | `taskbreak_bridge` 13 | new |
| TB-PLAN-FEATURE | a chunk feature overrides the plan feature | `taskbreak_bridge` 14 | new |
| TB-PLAN-BADJSON | a plan that is not valid JSON is refused | `taskbreak_bridge` 15 | new |
| TB-PLAN-VERSION | the plan schema version must be 1 | `taskbreak_bridge` 16 | new |

## `harness` CLI

Source: [ARCHITECTURE.md § `harness` CLI](ARCHITECTURE.md#harness-cli).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| H-CLEAN-HOT | `clean hot` empties the hot area, keeps persistent tests | `harness_wiring` 5, `harness_cli` 5 | covered |
| H-CONFIG | `config` prints the resolved wiring as JSON | `harness_cli` 1 | new |
| H-STATUS | `status` prints resolved paths and existence markers | `harness_cli` 2 | new |
| H-CLEAN-STATE | `clean state` refuses while items are in process | `harness_cli` 3 | new |
| H-CLEAN-STATE-TEAM | `clean state` counts live team tasks as in-process | `harness_cli` 7 | new |
| H-CLEAN-FORCE | `clean state --force` cleans anyway | `harness_cli` 4 | new |
| H-CLEAN-ALL | `clean all` empties hot, state, and artifacts | `harness_cli` 6 | new |
| H-CLEAN-DEFAULT | a bare `clean` defaults to the hot target | `harness_cli` 8 | new |

## Wiring (`wiring.py`)

Source: [ARCHITECTURE.md § Resolution Order](ARCHITECTURE.md#resolution-order-python-toolswiringpy).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| W-SELF-HOST | the pack config points at the pack's project | `harness_wiring` 1 | covered |
| W-PROJECT | a project config resolves that project's roots | `harness_wiring` 2 | covered |
| W-NEAREST | the nearest `harness.json` walking up wins | `harness_wiring` 3 | covered |
| W-ENV-STATE | `SWARM_STATE_ROOT` overrides the state root | `harness_wiring` 4 | covered |
| W-MALFORMED | a malformed config raises a wiring error | `harness_wiring` 6 | covered |
| W-CONFIG-MISSING | `SWARM_CONFIG` pointing at a missing file is an error | `harness_wiring` 7 | new |
| W-PACK | `SWARM_PACK` selects the pack config | `harness_wiring` 8 | new |
| W-DEFAULTS | absent fields fall back to the documented defaults | `harness_wiring` 9 | new |
| W-ENV-WORKSPACE | `SWARM_WORKSPACE` overrides the workspace root | `harness_wiring` 10 | new |
| W-ENV-HOT | `SWARM_HOT` overrides the hot tests root | `harness_wiring` 11 | new |
| W-KIND | `persistent_test_root()` selects harness vs project by `kind` | `harness_wiring` 12, 13 | new |

## TS wiring (`.opencode/lib/wiring.ts`)

Source: [TOOLS.md § opencode bridges](TOOLS.md) and
[ARCHITECTURE.md § Wiring](ARCHITECTURE.md#wiring).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| TS-CONFIG-WALKUP | with no start the TS resolver walks up to the nearest config | `ts_wiring` 1 | new |
| TS-CONFIG-PACK | with no start and no config above it, the TS resolver falls back to the pack config | `ts_wiring` 2 | new |

## Durable store (`durable_store.py`)

Source: [ARCHITECTURE.md § Durable Store](ARCHITECTURE.md#durable-store-toolsdurable_storepy).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| D-TIME | `iso_now()` returns a UTC `YYYY-MM-DDTHH:MM:SSZ` stamp | `durable_store` 1 | new |
| D-ATOMIC | `write_json_atomic` never leaves a partial file | `durable_store` 2 | new |
| D-READ | `read_json`/`list_json` return sorted non-dot JSON files | `durable_store` 3 | new |
| D-SEQ | `next_seq` increments a monotonic counter | `durable_store` 4 | new |
| D-LOCK | `lock` excludes a second holder | `durable_store` 5 | new |
| D-CLI-ERROR | `run_cli` renders tool errors as exit 2 | `durable_store` 6 | new |

## Acceptance pipeline

Source: [TESTING.md § Acceptance Pipeline](TESTING.md#acceptance-pipeline).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| A-PARSE-SHAPE | the parser emits the documented JSON IR shape | `acceptance_pipeline` 1 | new |
| A-PARSE-NOFEATURE | a file with no feature declaration is rejected | `acceptance_pipeline` 2 | new |
| A-PARSE-EXAMPLES | examples outside a scenario are rejected | `acceptance_pipeline` 3 | new |
| A-PARSE-RAGGED | a ragged example row is rejected | `acceptance_pipeline` 4 | new |
| A-DRY-DUP | duplicate-in-scenario is reported by default | `acceptance_pipeline` 5 | new |
| A-DRY-EXACT | exact duplicates are reported only with `--include-exact` | `acceptance_pipeline` 6 | new |
| A-DRY-VARIANT | placeholder variants are reported | `acceptance_pipeline` 7 | new |
| A-GEN-EXAMPLES | the generator emits one test per example | `acceptance_pipeline` 8 | new |
| A-MUTATE | the mutator changes example values and the suite catches it | `acceptance_pipeline` 9 | new |

## Concurrency contracts

Source: [ARCHITECTURE.md § Concurrency And Locking](ARCHITECTURE.md#concurrency-and-locking).

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| MAIL-PULL-CONCURRENT | two sessions pulling one role at the same time leave exactly one owner; the loser is refused as a foreign owner naming the winner | `duplicate_dispatch` 1 | new |
| MAIL-SEND-CONCURRENT | two identical handoffs sent concurrently queue exactly one item; the other reports `DUPLICATE` | `lock_contention` 1 | new |
| TEAM-JOURNAL-CONCURRENT | two concurrent journal appends to one worker chunk land with distinct sequence numbers | `lock_contention` 2 | new |

## Protocol constants

| Requirement | Behavior | Feature | Status |
|---|---|---|---|
| P-WAKE | the wake lines are constant and carry no task | not executable (prompt/protocol constant) | n/a |

## Increment Log

- **Increment 1 (mailbox)** - `mail_queue.feature` (14 scenarios, 15
  executions) and `mail_validation.feature` (8 scenarios, 14 executions).
  Parsed and dry-checked clean of exact/placeholder/near-duplicate findings;
  only `possible-synonym` advisories remain.

- **Increment 2 (team)** - `team_seat_routing.feature` (11 scenarios, 13
  executions), `team_context_delivery.feature` (5 scenarios, 5 executions),
  `team_mentor_exchange.feature` (4 scenarios, 5 executions),
  `team_oracle_attempt.feature` (7 scenarios, 7 executions), and
  `team_input_write_once.feature` (3 scenarios, 8 executions). All parse and
  dry-check clean of exact/placeholder/near-duplicate findings; only
  `possible-synonym` advisories remain. `team_open`'s section extraction is the
  remaining team gap (next increment).

- **Increment 3 (task-breaker bridge)** - `taskbreak_bridge.feature` (16
  scenarios, 22 executions). Parses and dry-checks clean of
  exact/placeholder/near-duplicate findings; only `possible-synonym` advisories
  remain.

- **Increment 4 (harness CLI and wiring)** - `harness_cli.feature` (6
  scenarios, 13 executions) and `harness_wiring.feature` (13 scenarios, 13
  executions). The varying scenarios became `Scenario Outline`s with `Examples`
  so `gherkin-mutator` has example cells to mutate: status row/marker, clean
  target/exit code, `SWARM_*` override variable, and the persistent-root
  `kind`. Both parse and dry-check clean of exact/placeholder/near-duplicate
  findings; only `possible-synonym` advisories remain.

- **Increment 5 (durable store and acceptance pipeline)** - `durable_store.feature`
  (6 scenarios, 11 executions) and `acceptance_pipeline.feature` (9 scenarios,
  13 executions). Both parse and dry-check clean of
  exact/placeholder/near-duplicate findings; only `possible-synonym` advisories
  remain. The acceptance-pipeline scenarios drive the vendored
  `gherkin-parser`, `ir-dry-checker`, `gherkin-mutator`, and the project
  `generator.py` through the acceptance runtime.

- **Increment 6 (team open sections)** - `team_open_sections.feature` (6
  scenarios, 11 executions). Parses and dry-checks clean of
  exact/placeholder/near-duplicate findings; only `possible-synonym` advisories
  remain. `open` resolves each task field from explicit flags first, then from
  the brief/design section headings.

- **Increment 7 (M10 known limitations)** - six scenarios across three features:
  `task_state_layout` 11-13 (no dead seal flag; `bind`/`close` find a task filed
  under an earlier date), `harness_cli` 7 (`clean state` counts live team tasks),
  and the new `ts_wiring.feature` 1-2 (no-start walk-up and pack fallback). All
  parse and dry-check clean of exact/placeholder/near-duplicate findings; only
  `possible-synonym` advisories remain. This closes the four entries in
  [ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations) except
  the accepted cosmetic `--ready` phantom seat.

- **Increment 8 (M10 tool/state contract audit)** - eight audited contract
  scenarios: `mail_queue` 15-17 (`done` refuses a foreign owner and names the
  holder; `done --id` completes only the named in-process item; `status` reports
  the in-process holder session), the new `team_command_validation.feature` 1-4
  (`open` validates the role and the task name, `bind` validates the seat, and
  only the worker seat may append worker journal kinds), and `harness_cli` 8 (a
  bare `clean` defaults to the hot target). No tool behavior changed: every
  contract pre-existed in `mailbox.py`, `team.py`, and `harness`, so this slice
  added step handlers and focused unit tests only. All parse and dry-check clean
  of exact/placeholder/near-duplicate findings; only `possible-synonym`
  advisories remain.

- **Increment 9 (M10 stress recovery)** - nine recovery scenarios across two new
  features: `mail_recovery` 1-5 (`done` without an in-process item is refused and
  leaves the queue; a completed item is never re-claimed; a re-send after
  completion is a new item; a corrupt queued or in-process item is refused
  naming `corrupt` and nothing moves) and `team_recovery` 1-4 (a session-resolved
  `context`/`done` finds a task filed under an earlier UTC date; the coder full
  payload carries its identity line with `TASK` still first; a repeated `done`
  appends and reports `NO_TASK`; a corrupt `task.json` fails a `bind` naming
  `corrupt`). Both parse and dry-check clean of exact/placeholder/near-duplicate
  findings; only `possible-synonym` advisories remain. `mailbox.read_item` and
  `team.load_task_json` are the single fail-closed readers for mail items and
  task records; the coder identity line is appended after the fixed 11-section
  payload so `TASK` stays first.

- **Increment 10 (M10 concurrency)** - three concurrency scenarios across two new
  features: `duplicate_dispatch` 1 (two sessions pull one role as separate
  operating-system processes; exactly one claims the item and becomes owner, and
  the loser is refused as a foreign owner naming the winner, exit 2) and
  `lock_contention` 1-2 (two identical handoffs sent concurrently queue exactly
  one item while the other reports `DUPLICATE`; two concurrent journal appends to
  one worker chunk land with distinct sequence numbers). The per-role and
  per-task guards are the real `durable_store.lock` `flock`; no tool behavior
  changed, so this slice added step handlers and focused unit tests only. Both
  features parse and dry-check clean of exact/placeholder/near-duplicate
  findings; only `possible-synonym` advisories remain. With the 47 property tests
  and these contracts, M10's stress/concurrency exit criteria are met.
