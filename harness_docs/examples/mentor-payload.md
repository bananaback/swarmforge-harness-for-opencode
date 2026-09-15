# Example — Mentor Payload

What a bound mentor receives from `team_context` (full mode). A fixed system
prompt followed by five sections, assembled from `task.json` and the journal with
no model call. See [TOOLS.md § Mentor Payload](../TOOLS.md#mentor-payload-system-prompt--5-sections).

The task below is illustrative.

```
You are the mentor seat. Advise from the task and chunk state below; answer the worker's ask with the failure evidence in view.
GOAL
every periods.feature scenario green end to end; unit covers every scenario
and every contract rule; regression baseline stays green; ruff clean.
oracle: cwd project_tests/persistent · python3 -m pytest -q
RULES
spec (verbatim; authoritative)
  Feature: Billing period bounds
    PER-1 valid month bounds        2026-09 / 2024-02 / 2026-12 -> first day, last day
    PER-2 malformed month rejected  "2026-9", "202609", " 2026-09", "2026-13", "2026-00"
    PER-3 first day of a month      "2026-09" -> 2026-09-01
frozen interface
  class BillingError(ValueError) · def month_start(text: str) -> date
  def month_bounds(text: str) -> tuple[date, date]
allowlist
  edit   src/billing/periods.py · tests/unit/** · tests/acceptance/**
  gen    hot_tests/** (regenerate; never hand-edit)
  read   src/billing/invoices.py:80-96
  never  any other src/billing file · .git · pyproject · CI · existing tests
TRAIL
readback: {"goal": "strict YYYY-MM parse; malformed -> BillingError; caller consumes month_bounds"}
plan: {"choice": "shape pre-check, then date(year, month, 1)", "falsifiers": "PER-1/3 red -> too strict; PER-2 no raise -> no check", "rationale": "strptime accepts 2026-9, which PER-2 fails"}
result: {"attempt": 1, "cmd": "python3 -m pytest unit -q", "exit": 1, "refs": ["attempt-01.txt"], "reading": "shape pre-check missing"}
ASK
why does the parser reject "2026-9"? should the shape check live in month_start or month_bounds?
FAILURE
tests/unit/test_periods.py::test_reject_unpadded
AssertionError: BillingError not raised for "2026-9"
got: datetime.date(2026, 9, 1)
```

Notes:

- Line 1 is the constant system prompt. The five section headers follow in order:
  `GOAL`, `RULES`, `TRAIL`, `ASK`, `FAILURE`.
- `GOAL` and `RULES` come from `task.json`'s `mentor` fields, captured at
  `team_open` from the `--goal`/`--rules` flags or the brief's `GOAL`/`RULES`
  sections. They are the sealed decision frame.
- `TRAIL` is every **worker-kind** journal entry (`readback`, `plan`, `result`,
  `note`) in sequence order, each rendered as `<kind>: <json>` with only its
  payload fields. If there are none it prints `no trail`.
- `ASK` prefers `mentor.ask`, else the latest `stuck` entry's message, else
  `no ask`.
- `FAILURE` prefers `mentor.failure`, else the latest `stuck` entry's
  `failure`/`evidence` field, else the content of that entry's first ref file,
  else `no failure`. Evidence is reproduced verbatim.
- The payload is stable across repeated full calls: it is computed before the
  `advice` entry is appended, and `TRAIL` excludes non-worker kinds.
- **Design rule.** Remove a field and test it: if the mentor can still rule, the
  field was redundant; if it would have to guess the goal, the rules, what
  happened, or what is being asked, the field was load-bearing.
