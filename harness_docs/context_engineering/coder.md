```text
TASK
  Implement strict month parsing and bounds for the billing service.
  Work on branch feat/periods. Do not switch branches or commit.

DEFINITION OF DONE
  1. Acceptance: every scenario in INPUTS.feature executes green end to end —
     parse -> project generator -> generated entrypoints run from <hot>.
  2. Unit: tests you author cover every feature scenario and every INTERFACE CONTRACT
     rule; unit suite -> 0 failed, 0 errors. You write the tests; no test cases are
     prescribed beyond the behavior above.
  3. Red observed: your first oracle run of the new tests failed for the expected
     reason and was recorded (attempt N) before implementation edits began.
  4. Regression: the existing suite stays green — 14 baseline + yours, 0 failed.
  5. Lint: ruff wrapper -> All checks passed.
  6. Digest journaled in RESULT shape below; mail pointer <= 300 chars to refactorer.
     Leave the tree dirty; no commit.

RESOLVED PATHS (authoritative; generated from harness.json at chunk open, verified)
  <workspace>        /work/billing-service
  <pack>             /opt/swarm-forge-tin
  <source>           /work/billing-service/src
  <persistent-root>  /opt/swarm-forge-tin/project_tests/persistent
  <unit>             <persistent-root>/unit
  <acceptance>       <persistent-root>/acceptance
  <features>         <persistent-root>/features
  <artifacts>        /work/billing-service/.artifacts
  <hot>              /opt/swarm-forge-tin/hot_tests
  <python>           /usr/bin/python3.12   (3.12.4)
  Source of truth: harness.json (pack root nearest upward, or SWARM_CONFIG / SWARM_PACK).
  Use these values verbatim. Never run harness status, find, or search for paths.
  When both harness and project persistent roots exist, use the project root.
  A path or cwd that is missing -> stop and report; never guess a substitute.

INPUTS (source of truth)
  feature    <features>/periods.feature         <- specifier delivery, immutable
  IR         <artifacts>/periods.json           <- parsed from the feature
  dry-check  <artifacts>/periods.dry.json -> clean
  caller     <source>/billing/invoices.py:80-96 <- ValueError contract
  If any input is missing or the dry-check is not clean, stop and report.

FEATURE (inlined; do not edit)
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
        |          |
        |  2026-09 |
        | 2026-13  |
        | 2026-00  |

    # PER-3 month start
    Scenario: PER-3 first day of a valid month
      Given the month "2026-09"
      When I ask for its start
      Then the first day is 2026-09-01

ACCEPTANCE DELIVERY (yours to build and run)
  - Runtime and step handlers live under <acceptance>/; the generator follows the APS
    contract and writes entrypoints into <hot>/. Step handlers: regex parameters by
    default; one handler per repeated step shape.
  - Running acceptance means: parse feature -> generate entrypoints -> run generated
    tests from <hot>. Never hand-edit generated entrypoints.

INTERFACE CONTRACT (what Gherkin cannot express; binding)
  module  <source>/billing/periods.py
    class BillingError(ValueError)
    def month_start(text: str) -> date
    def month_bounds(text: str) -> tuple[date, date]
  rules
    - Non-str input of any kind (None, 202609, []) -> TypeError before validation.
    - Error messages are not contract: tests assert exception type, never str(exc).
    - Frozen: names, signatures, BillingError name and base.
    - Stdlib only; no new dependencies. Out of scope: weeks, quarters, ranges,
      timezones, locales, CLI.
  Notes below answer how only. They may not introduce behavior the feature or this
  contract does not express; if a note implies a new "what", the note is wrong.
  Implementation notes
    - Validate the exact "YYYY-MM" shape first; reject before date construction.
    - Construct date(year, month, 1) in try/except ValueError and re-raise as
      BillingError so shape-valid/month-invalid rows (PER-2) cannot leak ValueError.
    - Last day via calendar.monthrange or next-month-minus-one-day.
  Your call: helper decomposition, regex vs manual slicing, test authoring style.

FILES
  create/edit  <source>/billing/periods.py · <unit>/** · <acceptance>/**
  generated    <hot>/** (regenerate, never hand-edit)
  read         <source>/billing/invoices.py:80-96 · <source>/billing/taxes.py:12-40 ·
               <unit>/test_taxes.py:1-30 (style to copy)
  never        <source>/billing/invoices.py or any <source>/billing/ file other than
               periods.py · .git/ · pyproject.toml · CI config · existing tests
  immutable    the feature file · the parse/generate/run commands · tests after the
               first green (never edit tests to make a run pass)

HOW TO RUN (each line gives cwd and exact command)
  Protocol:    tests first -> record the failing run -> minimal implementation ->
               green -> regression. Red before green is required evidence.
  Unit:        cwd <persistent-root> · PYTHONDONTWRITEBYTECODE=1 <python> -m pytest unit -q
  Regression:  cwd <persistent-root> · PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -q
  Acceptance:  cwd <workspace> · <pack>/tools/gherkin-parser <features>/periods.feature <artifacts>/periods.json
               cwd <workspace> · <pack>/tools/ir-dry-checker <artifacts>/periods.json <artifacts>/periods.dry.json
               cwd <acceptance> · <python> generate.py <artifacts>/periods.json
               cwd <workspace> · <python> -m pytest <hot>/periods_test.py -q
  Lint:        cwd <workspace> · <pack>/tools/ruff4py <source> <persistent-root>
               (the wrapper supplies `check`; never pass it)
  Runtime:     pytest 8.2 · offline · no pip install · stdlib only.
  Command output appears in this session; read it before deciding the next step.

CURRENT STATE (confirm before writing)
  Branch feat/periods at a1b2c3d; working tree clean; existing suite 14 passed.
  <source>/billing/periods.py and <unit>/test_periods.py do not exist yet.
  Confirm branch, commit, and that every RESOLVED PATH exists and matches before your
  first edit. Mismatch -> stop and report; do not proceed on it.

PRIOR ATTEMPT (do not repeat; omitted when the task has no durable history)
  Session 3 used datetime.strptime(text, "%Y-%m"). Rejected: strptime accepts
  "2026-9" and "2026-09-01" (PER-2 fails). Diff was reverted. Rule: reject the shape
  before parsing.

WHEN STUCK / BUDGET
  - Same failure signature twice in a row -> stop.
  - 5 failed oracle runs total, regardless of signature -> stop.
  - Then ask one question: what you tried, exact command, output, file:line. Never ask
    "is my code correct" — the oracle answers that. Interface, scope, or dependency
    doubt: stop and ask before guessing. Use the standard escalation route; this doc
    only sets the ask content.

WHEN DONE
  Journal a RESULT digest (uncapped) and keep the mail message <= 300 chars pointing
  to it:
    RESULT
      files: [/work/billing-service/src/billing/periods.py,
              /opt/swarm-forge-tin/project_tests/persistent/unit/test_periods.py,
              /opt/swarm-forge-tin/project_tests/persistent/acceptance/steps.py,
              /opt/swarm-forge-tin/hot_tests/periods_test.py]
      attempts: [{n: 1, cmd: "pytest unit -q", exit: 1,
                  reason: "PER-1..PER-3 not implemented"}, {n: 2, cmd: "...", exit: 0}]
      acceptance: periods.feature -> <hot>/periods_test.py -> all scenarios passed
      unit: 0 failed · regression: 14 baseline + new, 0 failed · ruff: clean
  Preserve the task name; hand off to refactorer with the digest pointer. Do not commit.

UPDATES (delta — not part of this pull)
  Advice, attempt results, journal entries, and contract revisions arrive later as
  append-only deltas after each tool call; this first payload contains none of them.
  Once written they are durable, so a resumed session reads them as history — never
  as first-turn content.
```

---

**FIRST TURN / LIFECYCLE**
```text
dispatch : system prompt + "TEAM_WAITING: run team_pull"   (the message carries no task)
turn 1   : team_pull -> chunk item; team_context -> the full payload below
later    : team_send ask -> ask queued; mentor brief arrives on the next pull; every
           step is written by tools, never by hand, and the session is append-only
```

**TASK** *— orchestrator: passes this block as a param to the chunk-open tool; the tool copies it into the sealed item.*
```text
  Implement strict month parsing and bounds for the billing service.
  Work on branch feat/periods. Do not switch branches or commit.
```

**DEFINITION OF DONE** *— fixed as workflow; if something changes here we must remember to update this too.*
```text
  1. Acceptance: every scenario in INPUTS.feature executes green end to end —
     parse -> project generator -> generated entrypoints run from <hot>.
  2. Unit: tests you author cover every feature scenario and every INTERFACE CONTRACT
     rule; unit suite -> 0 failed, 0 errors. You write the tests; no test cases are
     prescribed beyond the behavior above.
  3. Red observed: your first oracle run of the new tests failed for the expected
     reason and was recorded (attempt N) before implementation edits began.
  4. Regression: the existing suite stays green — 14 baseline + yours, 0 failed.
  5. Lint: ruff wrapper -> All checks passed.
  6. Digest journaled in RESULT shape below; mail pointer <= 300 chars to refactorer.
     Leave the tree dirty; no commit.
```

**RESOLVED PATHS** *— orchestrator: calls the wiring tool with its context; the tool resolves and verifies these from harness.json and passes the block through.*
```text
  <workspace>        /work/billing-service
  <pack>             /opt/swarm-forge-tin
  <source>           /work/billing-service/src
  <persistent-root>  /opt/swarm-forge-tin/project_tests/persistent
  <unit>             <persistent-root>/unit
  <acceptance>       <persistent-root>/acceptance
  <features>         <persistent-root>/features
  <artifacts>        /work/billing-service/.artifacts
  <hot>              /opt/swarm-forge-tin/hot_tests
  <python>           /usr/bin/python3.12   (3.12.4)
  Source of truth: harness.json (pack root nearest upward, or SWARM_CONFIG / SWARM_PACK).
  Use these values verbatim. Never run harness status, find, or search for paths.
  When both harness and project persistent roots exist, use the project root.
  A path or cwd that is missing -> stop and report; never guess a substitute.
```

**INPUTS** *— orchestrator: collects from the specifier mail (feature, IR, dry state) and the design touch points; the tool inlines the resolved paths.*
```text
  feature    <features>/periods.feature         <- specifier delivery, immutable
  IR         <artifacts>/periods.json           <- parsed from the feature
  dry-check  <artifacts>/periods.dry.json -> clean
  caller     <source>/billing/invoices.py:80-96 <- ValueError contract
  If any input is missing or the dry-check is not clean, stop and report.
```

**FEATURE** *— the inputs, inlined verbatim by the tool so the coder does not need to explore; immutable.*
```text
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
        |          |
        |  2026-09 |
        | 2026-13  |
        | 2026-00  |

    # PER-3 month start
    Scenario: PER-3 first day of a valid month
      Given the month "2026-09"
      When I ask for its start
      Then the first day is 2026-09-01
```

**ACCEPTANCE DELIVERY** *— fixed as workflow (APS contract); identical across coder dispatches.*
```text
  - Runtime and step handlers live under <acceptance>/; the generator follows the APS
    contract and writes entrypoints into <hot>/. Step handlers: regex parameters by
    default; one handler per repeated step shape.
  - Running acceptance means: parse feature -> generate entrypoints -> run generated
    tests from <hot>. Never hand-edit generated entrypoints.
```

**INTERFACE CONTRACT** *— orchestrator: composes the design chunk for this task and passes it as a param; the tool seals it into the pack.*
```text
  module  <source>/billing/periods.py
    class BillingError(ValueError)
    def month_start(text: str) -> date
    def month_bounds(text: str) -> tuple[date, date]
  rules
    - Non-str input of any kind (None, 202609, []) -> TypeError before validation.
    - Error messages are not contract: tests assert exception type, never str(exc).
    - Frozen: names, signatures, BillingError name and base.
    - Stdlib only; no new dependencies. Out of scope: weeks, quarters, ranges,
      timezones, locales, CLI.
  Notes below answer how only. They may not introduce behavior the feature or this
  contract does not express; if a note implies a new "what", the note is wrong.
  Implementation notes
    - Validate the exact "YYYY-MM" shape first; reject before date construction.
    - Construct date(year, month, 1) in try/except ValueError and re-raise as
      BillingError so shape-valid/month-invalid rows (PER-2) cannot leak ValueError.
    - Last day via calendar.monthrange or next-month-minus-one-day.
  Your call: helper decomposition, regex vs manual slicing, test authoring style.
```

**FILES** *— from the design chunk params, reconciled against parallel chunks by the tool.*
```text
  create/edit  <source>/billing/periods.py · <unit>/** · <acceptance>/**
  generated    <hot>/** (regenerate, never hand-edit)
  read         <source>/billing/invoices.py:80-96 · <source>/billing/taxes.py:12-40 ·
               <unit>/test_taxes.py:1-30 (style to copy)
  never        <source>/billing/invoices.py or any <source>/billing/ file other than
               periods.py · .git/ · pyproject.toml · CI config · existing tests
  immutable    the feature file · the parse/generate/run commands · tests after the
               first green (never edit tests to make a run pass)
```

**HOW TO RUN** *— fixed as workflow; the orchestrator resolves the tokens into exact commands at chunk open.*
```text
  Protocol:    tests first -> record the failing run -> minimal implementation ->
               green -> regression. Red before green is required evidence.
  Unit:        cwd <persistent-root> · PYTHONDONTWRITEBYTECODE=1 <python> -m pytest unit -q
  Regression:  cwd <persistent-root> · PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -q
  Acceptance:  cwd <workspace> · <pack>/tools/gherkin-parser <features>/periods.feature <artifacts>/periods.json
               cwd <workspace> · <pack>/tools/ir-dry-checker <artifacts>/periods.json <artifacts>/periods.dry.json
               cwd <acceptance> · <python> generate.py <artifacts>/periods.json
               cwd <workspace> · <python> -m pytest <hot>/periods_test.py -q
  Lint:        cwd <workspace> · <pack>/tools/ruff4py <source> <persistent-root>
               (the wrapper supplies `check`; never pass it)
  Runtime:     pytest 8.2 · offline · no pip install · stdlib only.
  Command output appears in this session; read it before deciding the next step.
```

**CURRENT STATE** *— generated by the tool at chunk open (git + baseline run); the coder must re-confirm it.*
```text
  Branch feat/periods at a1b2c3d; working tree clean; existing suite 14 passed.
  <source>/billing/periods.py and <unit>/test_periods.py do not exist yet.
  Confirm branch, commit, and that every RESOLVED PATH exists and matches before your
  first edit. Mismatch -> stop and report; do not proceed on it.
```

**PRIOR ATTEMPT** *— read from the durable attempt artifacts of this task; absent on a first-ever run.*
```text
  Session 3 used datetime.strptime(text, "%Y-%m"). Rejected: strptime accepts
  "2026-9" and "2026-09-01" (PER-2 fails). Diff was reverted. Rule: reject the shape
  before parsing.
```

**WHEN STUCK / BUDGET** *— fixed as workflow policy (stop caps + ask content); the escalation route stays in the standing prompt.*
```text
  - Same failure signature twice in a row -> stop.
  - 5 failed oracle runs total, regardless of signature -> stop.
  - Then ask one question: what you tried, exact command, output, file:line. Never ask
    "is my code correct" — the oracle answers that. Interface, scope, or dependency
    doubt: stop and ask before guessing. Use the standard escalation route; this doc
    only sets the ask content.
```

**WHEN DONE** *— fixed as workflow contract: digest shape, mail cap, and handoff target.*
```text
  Journal a RESULT digest (uncapped) and keep the mail message <= 300 chars pointing
  to it:
    RESULT
      files: [/work/billing-service/src/billing/periods.py,
              /opt/swarm-forge-tin/project_tests/persistent/unit/test_periods.py,
              /opt/swarm-forge-tin/project_tests/persistent/acceptance/steps.py,
              /opt/swarm-forge-tin/hot_tests/periods_test.py]
      attempts: [{n: 1, cmd: "pytest unit -q", exit: 1,
                  reason: "PER-1..PER-3 not implemented"}, {n: 2, cmd: "...", exit: 0}]
      acceptance: periods.feature -> <hot>/periods_test.py -> all scenarios passed
      unit: 0 failed · regression: 14 baseline + new, 0 failed · ruff: clean
  Preserve the task name; hand off to refactorer with the digest pointer. Do not commit.
```

**UPDATES** *— delta only: produced by tool calls during the session; never present in the first pull.*
```text
  team_send ask        -> ask queued; mentor brief arrives on the next pull
  team_context --delta -> ADVICE: <ruling>            (append-only, durable after written)
  team_attempt         -> ATTEMPT: N (exit, signature, refs)
  team_journal         -> JOURNAL: seq N, kind, entry
  contract revision    -> re-sealed only by the orchestrator; arrives as a binding delta
  A resumed session reads all of the above as history — first-turn content stays as
  the full pull above.
```
