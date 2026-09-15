# Example — Coder Payload

What a bound coder receives from `team_context` (full mode) on a coder task.
Eleven sections, fixed order, assembled only from `task.json` and the resolved
harness config. See [TOOLS.md § Coder Payload](../TOOLS.md#coder-payload-11-sections-fixed-order).

The task below is illustrative; real values come from the chunk's `task.json`
and `input/` files.

```
TASK
feature/periods
Implement strict month parsing and bounds for the billing service.
Work on branch feat/periods. Do not switch branches or commit.
DEFINITION OF DONE
1. Acceptance: every scenario in the feature executes green end to end.
2. Unit: tests cover every scenario and every INTERFACE CONTRACT rule; 0 failed.
3. Red observed: the first oracle run failed for the expected reason before edits.
4. Regression: the existing suite stays green.
5. Lint: ruff wrapper -> All checks passed.
6. Digest journaled; mail pointer <= 300 chars. Leave the tree dirty.
RESOLVED PATHS
workspace root: /work/billing-service
state root: /opt/swarm-forge-tin/.swarmforge
artifacts root: /opt/swarm-forge-tin/dump
hot tests root: /opt/swarm-forge-tin/hot_tests
persistent test root: /opt/swarm-forge-tin/project_tests/persistent
INPUTS
brief.md
periods.feature
periods.json
design.md
FEATURE
Feature: Billing period bounds

  # PER-1 valid month bounds
  Scenario Outline: PER-1 bounds of a valid month
    Given the month "<month>"
    When I ask for its bounds
    Then the first day is <first> and the last day is <last>

    Examples:
      | month   | first      | last       |
      | 2026-09 | 2026-09-01 | 2026-09-30 |
      | 2024-02 | 2024-02-01 | 2024-02-29 |
      | 2026-12 | 2026-12-01 | 2026-12-31 |

  # PER-2 malformed month rejected
  Scenario Outline: PER-2 malformed month is rejected
    Given the month "<month>"
    When I ask for its bounds
    Then a BillingError is raised

    Examples:
      | month    |
      | 2026-9   |
      | 202609   |
      |  2026-09 |
      | 2026-13  |
      | 2026-00  |
INTERFACE CONTRACT
module  <source>/billing/periods.py
  class BillingError(ValueError)
  def month_start(text: str) -> date
  def month_bounds(text: str) -> tuple[date, date]
rules
  - Non-str input of any kind (None, 202609, []) -> TypeError before validation.
  - Error messages are not contract: tests assert exception type, never str(exc).
  - Frozen: names, signatures, BillingError name and base.
  - Stdlib only; no new dependencies.
FILES
create/edit  <source>/billing/periods.py · <unit>/** · <acceptance>/**
generated    <hot>/** (regenerate, never hand-edit)
read         <source>/billing/invoices.py:80-96
never        any other <source>/billing file · .git/ · pyproject.toml · CI config
immutable    the feature file · tests after the first green
HOW TO RUN
persistent: cd /opt/swarm-forge-tin/project_tests/persistent && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3.12 -m pytest
acceptance: /usr/bin/python3.12 /opt/swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py
lint: /opt/swarm-forge-tin/tools/ruff4py /work/billing-service/src /opt/swarm-forge-tin/project_tests/persistent
PRIOR ATTEMPT
--- attempt-01.txt ---
============================= test session starts ==============================
collected 6 items
tests/unit/test_periods.py ..FFFF                                          [100%]
...
WHEN STUCK
No attempt cap: keep the oracle loop running while progress is real.
When the next change would be a guess, ask one question with the exact command, output, and file:line.
Ask again after each brief; the pair keep talking until the path is clear.
Never ask 'is my code correct'; the oracle answers that.
Interface, scope, or dependency doubt: ask before guessing.
WHEN DONE
Journal a RESULT digest and keep the mail pointer <= 300 characters.
Hand off to refactorer with the digest pointer.
Leave the tree dirty; do not commit.
```

Notes:

- `TASK` is the task name followed by `task_text`; `task_text` is captured from
  the brief's `TASK` section at `team_open` (or the `--task-text` flag).
- `RESOLVED PATHS` reports configured values verbatim — it never touches the
  disk, so an absent configured root still appears.
- `INPUTS` lists the copied file names, not paths; the files themselves are under
  the chunk's `input/`.
- `FEATURE` is the verbatim content of the first `.feature` file in `input/`.
- `INTERFACE CONTRACT` prefers the copied design input, else `task.json`'s
  `interface_contract`. `FILES` prefers `files`, else the design input.
- `PRIOR ATTEMPT` inlines every `output/attempt-*.txt`, or `no prior attempt`.
- `HOW TO RUN` uses the `persistent test root` selected by
  [kind](../ARCHITECTURE.md#persistent-test-root-kind) and `sys.executable`.
- The payload applies only to a **coder** task's worker seat. A refactorer or
  architect chunk's worker receives the generic input-pack + journal payload
  instead.

## Lifecycle

```
dispatch : system prompt + "TEAM_WAITING: run team_pull"   (no task in the message)
turn 1   : team_pull -> chunk item (input pack); team_context -> this payload
later    : team_send ask -> ask queued; mentor brief arrives on the next pull;
           every step is written by tools, never by hand
```
