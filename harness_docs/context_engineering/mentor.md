```text
  SYSTEM PROMPT (constant; not part of the per-ask payload)
    ROLE       advise only. The oracle decides green, never your judgment.
    IMMUTABLE  tests and the oracle command — never ask for them to change.
    AUTHORITY  in-lane   a fix inside the frozen contract, the allowlist, and the spec.
               boundary  changing the frozen contract, editing outside the allowlist,
                         a new dependency -> you own this call; rule on it directly.
               disputed  spec and interface disagree, or a value's origin is unclear
                         -> verify before deciding; do not rule.
               rule      "status quo, nothing changes" is never a ruling.
    REPLY      one brief: ruling | assign-check | need | verify-then-decide. There is no
               senior tier: if the question is out of lane, state the boundary and rule.
               Never pick the least-bad out-of-lane option silently.
  ---------------------------------------------------------------------------

  GOAL (constant)
    done    every periods.feature scenario green end to end; unit covers every scenario
            and every contract rule; regression 14 baseline stays green; ruff clean.
    oracle  cwd project_tests/persistent · /usr/bin/python3.12 -m pytest -q
            scope: unit + acceptance (acceptance run after generation).

  RULES (constant)
    spec (verbatim; authoritative)
      Feature: Billing period bounds
        PER-1 valid month bounds        2026-09 / 2024-02 / 2026-12 -> first day, last day
        PER-2 malformed month rejected  "2026-9", "202609", "", " 2026-09", "2026-13", "2026-00"
        PER-3 first day of a month      "2026-09" -> 2026-09-01
      gap: no scenario takes a non-str month; none models a draft/empty period.
    frozen interface
      class BillingError(ValueError) · def month_start(text: str) -> date
      def month_bounds(text: str) -> tuple[date, date]
      rules: non-str input of any kind (None, 202609, []) -> TypeError before validation;
      messages are not contract; frozen names/signatures/base; stdlib only.
    allowlist
      edit   src/billing/periods.py · tests/unit/** · tests/acceptance/**
      gen    hot_tests/** (regenerate; never hand-edit)
      read   src/billing/invoices.py:80-96
      never  any other src/billing file · .git · pyproject · CI · existing tests

  TRAIL (the worker's own decision records; full on this pull, deltas after)
    n=1   readback  goal: strict YYYY-MM parse; malformed -> BillingError; caller
                    invoices.py:88 consumes month_bounds(row["period"]).
    n=10  plan      choice: shape pre-check, then date(year, month, 1).
                    assumptions: caller passes str; malformed arrives as str.
                    falsifiers: PER-1/3 red -> too strict; PER-2 no raise -> no check.
                    rationale: strptime accepts "2026-9" and "2026-09-01", which PER-2 fails.
                    expect: PER-1/3 green, PER-2 raises BillingError.
    n=12  result    attempt-01 · exit 1 · red 2/6: BillingError not raised for "2026-9"
                    reading: shape pre-check missing · refs attempts/01.output.txt
    n=20  result    attempt-02 · exit 0 · unit green (14 baseline + new)
    n=31  ask       are acceptance step handlers (tests/acceptance/) in the allowlist?
    n=33  advice    re 31 · yes; entrypoints go to hot_tests.
    n=40  plan      run acceptance; expect all scenarios green.
    n=42  result    attempt-03 · exit 1 · acceptance red:
                    TypeError: expected str, got NoneType
                      /work/billing-service/src/billing/invoices.py:88 in build_rows ->
                          month_bounds(row["period"])
                    reading: a row's period is None; month_bounds received None.
                    refs attempts/03.output.txt

  FAILURE (verbatim)
    cmd     oracle (above)
    fail    tests/acceptance/test_periods.py::test_periods_acceptance
            TypeError: expected str, got NoneType
              /work/billing-service/src/billing/invoices.py:88 in build_rows ->
                  month_bounds(row["period"])
    value   row["period"] is None
    origin  tests/acceptance/steps.py +18 (in allowlist) adds the row:
              + rows = [{"period": None}, {"period": ""}, {"period": "2026-09"}]
    diff    periods.py +96/-0 · steps.py +18/-0 · unit +22/-0
    ref     attempts/03.output.txt (full)

  ASK (verbatim from the worker; a proposal, not the option set)
    q        which layer owns the empty-period case?
    options  a) follow the contract: non-str -> TypeError propagates
             b) return None from the caller layer (invoices.py, outside allowlist)
             c) change the contract: None -> None
    read     the empty-period case is not covered by the feature.
```

---

**Design note.** Four delivered categories — `GOAL`, `RULES`, `TRAIL`, `ASK` (with its verbatim
`FAILURE` evidence) — plus a constant system prompt. `GOAL` and `RULES` are sealed at chunk open;
`TRAIL` arrives full on the first pull and as deltas after; `ASK` + `FAILURE` are the per-ask text. Every fact the advice can rest on is verbatim;
nothing states the conclusion. The advisor audits the ask against `RULES`; it is not told the
answer.

Remove-a-field test: if removing it still lets the advisor rule, it was redundant; if the advisor
would have to guess the goal, the rules, what happened, or what is being asked, it was
load-bearing.
