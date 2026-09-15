# Mutation rationale

`gherkin-mutator` is run on the mail and team acceptance features through the
project acceptance runner. Reports are reproducible under the artifacts root.

```text
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_mutation.py \
  --feature swarm-forge-tin/harness_tests/persistent/features/mail_validation.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/taskbreak_bridge.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_seat_routing.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_context_delivery.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_mentor_exchange.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_oracle_attempt.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_input_write_once.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/harness_cli.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/harness_wiring.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/durable_store.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/acceptance_pipeline.feature \
  --feature swarm-forge-tin/harness_tests/persistent/features/team_open_sections.feature
```

| Report | Total | Killed | Survived | Errors |
|---|---:|---:|---:|---:|
| `dump/mutation/mail_validation.json` | 41 | 27 | 14 | 0 |
| `dump/mutation/taskbreak_bridge.json` | 26 | 20 | 6 | 0 |
| `dump/mutation/team_seat_routing.json` | 51 | 44 | 7 | 0 |
| `dump/mutation/team_context_delivery.json` | 11 | 10 | 1 | 0 |
| `dump/mutation/team_mentor_exchange.json` | 17 | 11 | 6 | 0 |
| `dump/mutation/team_oracle_attempt.json` | 22 | 17 | 5 | 0 |
| `dump/mutation/team_input_write_once.json` | 9 | 9 | 0 | 0 |
| `dump/mutation/harness_cli.json` | 24 | 24 | 0 | 0 |
| `dump/mutation/harness_wiring.json` | 5 | 5 | 0 | 0 |
| `dump/mutation/durable_store.json` | 25 | 23 | 2 | 0 |
| `dump/mutation/acceptance_pipeline.json` | 40 | 22 | 18 | 0 |
| `dump/mutation/team_open_sections.json` | 22 | 18 | 4 | 0 |

The portable mutator only mutates example-cell values; it never mutates step
text. Every survivor below is a **semantically equivalent mutation**: the cell
is an input the scenario never asserts against a fixed expectation, or the
value moves together with the expectation, so no asserted behavior changes. No
survivor points at a defect in `team.py`, `mailbox.py`, `taskbreak.py`, or a
step handler. No source edit was made to fit a scenario.

## `mail_validation` — 14 survivors, all in "Mail send validation 1"

That scenario lists one problem per row. The `problem` cell is the only fixed
expectation; `from`, `to`, `task`, and `priority` are the inputs that produce
the named problems. The step handler now asserts the **exact problem set**: it
compares the count of `- ` stderr lines to the expected problems, one-to-one and
in order, and requires each line to start with its expected problem (the tool
appends detail such as ``; got `5` `` that the feature abbreviates). Containment
alone let an extra problem line pass, so a mutated input that added a problem
survived; the count check kills those.

- `from` (1), `priority` (6), `task` (7): the mutation leaves the named problem
  set intact — an already-invalid sender stays invalid, a two-digit `priority`
  stays two digits or drops an unasserted problem, and a case-changed task keeps
  the same problem identity. The refusal and its problem set are unchanged.
- Every `problem` cell mutation (the fixed expectation) is killed. Every
  mutation that adds or removes a problem line is killed. All other validation
  scenarios (2-8) have a single `problem` column, and every mutation there is
  killed.

## `taskbreak_bridge` — 6 survivors, input-only or value-moving cells

| Cell | Scenario | Why the mutation is equivalent |
|---|---|---|
| `task` | 1, 8 | The Given and the Then read the same mutated cell, so the plan opens and reports the mutated task; the assertion moves with the value. |
| `role` | 6 | `designer` stays an unsupported role under a case change, so the refusal names the same fixed problem. |
| `reference` | 9 | Any value other than `brief` selects the feature-not-found fixture, which is exactly the row's expected problem. |
| `version` | 16 | `2 -> 10` is still not version 1, so the refusal names the same fixed problem. |

Every `problem` and `value` cell (the fixed expectations) is killed, and every
mutation that changes the refusal identity or the opened-task set is killed.


## `mail_queue` — 29 survivors (prior run)

| Class | Columns | Scenarios | Why the mutation is equivalent |
|---|---|---|---|
| Unasserted send content | `task`, `priority`, `message` | 1, 2, 4, 6, 9 | The scenario asserts routing (`QUEUED`, recipients), the pulled payload, or the waiting state; these cells are only inputs. |
| Resume scenario's second mail | `from`, `to` | 6 | The scenario asserts that pull resumes the already-claimed item; the second send's routing is never asserted, so a refused send changes nothing. |
| Result asserted by value | `result` | 8, 9 | `the completed item records result "<result>"` asserts the same mutated value, so recording it is unchanged. |
| Non-observed list item | `mails` | 5, 7, 8, 12, 13, 14 | The mutation changes an item the assertion does not observe (a lower-priority item, or a still-valid case change that keeps the claimed item / batch group identical). |
| Opaque session id | `owner`, `other` | 12, 13 | Session ids are opaque and used consistently for pull, refusal, and ownership assertions; a case change is equivalent. |

## `team_seat_routing` — 7 survivors, all opaque session/input cells

| Cells | Scenarios | Why the mutation is equivalent |
|---|---|---|
| `session` (`worker-1`, `mentor-1`) | 1 | The session id is opaque and used consistently for the bind and the status assertion; a case change binds and is reported under the mutated id. |
| `holder`, `session` | 2 | `holder` only seeds the Given bind; the assertions name the takeover `session` and its reset state, both carried by the mutated value. |
| `session` | 3 | The seat is already bound to `holder`, so the refused session's own value never reaches the named refusal. |
| `session` (`ghost`) | 6 | Any unbound session yields the same "not bound to any team seat" refusal. |
| `holder` | 11 | The ready list only reports that a seat has a session; the holder id is never asserted. |

Every `problem` cell (the fixed refusal text) and every `seat`/`task`/`line`
cell is killed.

## `team_context_delivery` — 1 survivor, an input-only message

| Cell | Scenario | Why the mutation is equivalent |
|---|---|---|
| `message` | 5 | The mentor's brief is dialogue and is never journaled; the assertion `the context does not carry "<message>"` carries the mutated value, which is still absent. |

Every `problem` (`LOAD_REQUIRED`), `mode`, `seat`, and `task` cell is killed.

## `team_mentor_exchange` — 6 survivors, input-only cells

| Cells | Scenario | Why the mutation is equivalent |
|---|---|---|
| `message` | 1 | The ask is journaled with the same mutated message and asserted against it; the value moves with the expectation. |
| `message` | 2 | A brief is not journaled; the message is input-only. |
| `kind`, `message` | 3 | The edge refusal names the *required* kind, not the given one; an invalid or case-changed kind still produces the same fixed refusal, and the message is never asserted. |

Every `problem`, `seat`, `task`, and `kind`-that-selects-the-edge cell is
killed.

## `team_oracle_attempt` — 5 survivors, input-only cells

| Cells | Scenario | Why the mutation is equivalent |
|---|---|---|
| `command` | 3 | The scenario only asserts that a dirty tree records a diff; the diff comes from git, not the command. |
| `timeout` (`0.5 -> 9.73`) | 5 | `sleep 30` still exceeds any positive timeout and is recorded as exit 124. |
| `attempt` (`9 -> 16`) | 7 | Any unknown attempt number is refused; the scenario asserts the failure, not the number. |
| `command`, `kind` | 7 | The Given only needs an attempt to exist; the command is not asserted and an invalid kind still fails journaling. |

Every `attempt` (1), `exit`, `output`, `name`, `timeout`-with-a-passing-assertion,
and `kind`-selecting-a-valid-entry cell is killed.

## `team_input_write_once` — 0 survivors

Every example cell is killed.

## `harness_cli` — 0 survivors

The outline parameterizes the status row/marker, the clean target/exit code, and
the generated-file/empty-directory targets. Every cell is killed. In scenario 3
the refusal must report the in-process item and name the state directory that
holds it; a case-changed `target` (`state -> staTe`) is refused by argparse
before the state check, so its usage error never names the item and is killed.
Every other `target` mutation (scenarios 5 and 6) is killed because the asserted
exit code or the named directory changes.

## `harness_wiring` — 0 survivors

The outline parameterizes the `SWARM_*` override variable and the persistent-root
`kind`. Every cell is killed: a misspelled override variable leaves the resolved
root at its configured value, and a misspelled `kind` fails the selected-root
comparison.

## `durable_store` — 2 survivors, both lock-name case changes

| Cell | Scenario | Why the mutation is equivalent |
|---|---|---|
| `held` (`mailbox -> mAilbox`) | 5, example 2 | That row holds `mailbox` and requests `journal`; the two names differ before and after the case change, so the second holder is still admitted. |
| `requested` (`journal -> journAl`) | 5, example 2 | Same: the requested name stays different from the held name, so the holder is still admitted. |

Every `start`, `calls`, `sequence`, `files`, `listing`, `problems`, `exit_code`,
`lines`, and `outcome` cell is killed. In scenario 5 the `held`/`requested`
mutations in example 1 (both `mailbox`) are killed, because a case change makes
the names differ and flips the outcome from blocked to admitted.

## `acceptance_pipeline` — 18 survivors, all input-only or value-moving cells

| Class | Cells | Scenarios | Why the mutation is equivalent |
|---|---|---|---|
| Value moves with the assertion | `name`, `scenario`, `step` | 1 | The same cell builds the feature file and names the parsed result, so the assertion moves with the mutated value. The `parameter` cell is the fixed expectation and every mutation is killed. |
| Rejection is content-independent | `line` | 2 | Any content without a `Feature:` declaration is rejected with exit 1, so changing the line keeps the same exit code. |
| Precondition stays ragged | `row_cells`, `header_cells` | 4 | The mutations preserve a ragged example row (`1/2 -> 6/11`, `3/2 -> 0/-7`), so the parser still rejects with exit 1. A mutation that made the counts equal would parse successfully and be killed. |
| Repeated step stays repeated | `scenarios`, `step` | 5, 6 | The IR still repeats the step in at least one scenario, so `duplicate-in-scenario` (scenario 5) and `exact-duplicate` with `--include-exact` (scenario 6) remain present; a single scenario still repeats the step twice, so `exact-duplicate` is still reported. |
| Mode falls back to default | `mode` | 6, example 1 | Only `with --include-exact` adds the flag; any other spelling is the default run, whose exact kind set is still `duplicate-in-scenario`. |

Every `parameter`, `exit_code`, `outcome`, `kind`, `kinds`, `tests`, `killed`,
`survived`, and `level` cell is killed. Scenario 6 now asserts the dry report
contains **only** the named kinds, so the `kinds` cell is a fixed expectation and
every mutation is killed. The scenario 9 cells drive a nested `gherkin-mutator`
run through `run_mutation.run_feature`, so an invalid `level` or a changed
expected count fails the generated test.

## `team_open_sections` — 4 survivors, all value-moving brief bodies

| Cell | Scenario | Why the mutation is equivalent |
|---|---|---|
| `value` (GOAL, RULES, ASK, FAILURE) | 3 | The same cell is written under the brief's section heading and then asserted back out of `task.json`; the assertion moves with the mutated value. |

Every `role`, `section`, and `style` cell is killed: an unknown role is refused
by `team.py`, a misspelled section is not extracted, and an unknown heading style
is rejected. Scenarios 1, 2, and 4 carry only the `role` column, so every
mutation there is killed.

## No defect behind any survivor

Each survivor above is a **semantically equivalent mutation**: an input the
scenario never asserts against a fixed expectation, a value that moves together
with its expectation, or a cell whose mutated value still satisfies the asserted
condition (a still-ragged row, a still-distinct lock name, or a still-default dry
run). No survivor points at a defect in `durable_store.py`, `wiring.py`,
`harness`, `team.py`, `gherkin-parser`, `ir-dry-checker`, the generator, or a
step handler. No source or feature file was edited to fit a mutation.
