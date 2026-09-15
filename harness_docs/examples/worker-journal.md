# Example — Worker Journal

A full chunk of worker journaling at full depth: three attempts, one ask, one
brief, green. The journal is **worker-authored only**; facts (cmd, exit, refs,
diff) are attached by the tool from the numbered attempt artifact.

The ask and brief are dialogue and live in the mentor's session turns — shown
between markers only to make the scenario readable. Worker prose is uncapped.

```
task backup-schedule · worker: coder · oracle: python3 -m pytest persistent/unit/test_dateparse.py -q

#1 readback  goal: parse_date(value) -> date for strict ISO YYYY-MM-DD; ValueError otherwise;
                 load_entries skips invalid entries
             constraints: [src/schedule/dateparse.py only; tests hash-pinned; no interface changes]
             done: oracle green
             understanding: load_entries reads each entry's "date" and must skip invalid ones.
             loader.py is outside my allowlist, so I cannot see whether it detects rejection by
             exception type or by sentinel. Test names suggest both are in play.

#2 plan      situation: parse_date is a stub; I need rejection semantics and a strict format check.
             options:
               A return None on invalid input
                 for: brief v2 says "reject invalid input"; test_loader_skips_invalid reads like a sentinel check
                 against: test_invalid_date_raises uses pytest.raises (line 42) — cannot pass with a return value
               B raise DateParseError(Exception)
                 for: the oracle clearly expects an exception; a domain error is explicit
                 against: DateParseError appears nowhere I can see
               C raise ValueError
                 for: pytest.raises(ValueError) matches line 42 exactly; Python convention
                 against: brief v2 does not name it; cannot verify loader.py catches it
               D strict regex pre-check + C
                 for: test_reject_unpadded implies "2026-2-3" must be rejected; strptime accepts it
                 against: more moving parts
             choice: A
             rationale: when the brief and the oracle point different ways the protocol says ask, not
             guess. Trying the literal brief first produces the cleanest ask evidence: if line 42 fails
             with DID NOT RAISE, the conflict is proven and the mentor gets a concrete question.
             falsifiers: line 42 red -> A wrong; line 55 red -> strptime too permissive
             change: wrap strptime; return None on ValueError
             expect: all 6 green if the brief reading is right; the specific bet is line 42

#3 result    attempt 1 · exit 1 · red 3/6
             cmd: python3 -m pytest persistent/unit/test_dateparse.py -q
             failures:
               test_invalid_date_raises  unit/test_dateparse.py:42
                 assert pytest.raises(ValueError): parse_date("2026-13-40")
                 E  Failed: DID NOT RAISE <class 'ValueError'>
               test_reject_unpadded      unit/test_dateparse.py:55
                 assert parse_date("2026-2-3") raises ValueError
                 got: datetime.date(2026, 2, 3)
             change: src/schedule/dateparse.py +8/-2
             reading: A is refuted twice — the loader neither catches exceptions nor skips None,
             so it must rely on parse_date raising something. Line 42 pins the type to ValueError.
             refs: attempt-01.txt · attempt-01.diff

── dialogue (mentor session turns, not journal) ──
 ask:  loader.py is outside my allowlist. Returning None is not skipped and DateParseError is not
       caught. Line 42 pins ValueError. Does load_entries catch ValueError?
 brief: load_entries catches ValueError and skips the entry. Brief v2 "return None" is stale — the
        oracle governs. Raise ValueError(f"invalid date: {raw}"); add the strict regex pre-check.
        One file: src/schedule/dateparse.py.
───────────────────────────────────────────────────────────────────────────────

#4 plan      situation: loader contract confirmed by mentor; strictness still to fix.
             options:
               C1 raise ValueError with the raw value
                 for: satisfies line 42 and the loader's catch
                 against: line 55 (unpadded) stays red — not enough alone
               C2 raise ValueError + regex pre-check for strict ISO
                 for: fixes line 55 too; strptime still validates the calendar
                 against: one more moving part
             choice: C2
             rationale: brief confirms C, and line 55 is already red, so C1 alone cannot be green.
             change: add ^\d{4}-\d{2}-\d{2}$ pre-check; DateParseError -> ValueError(f"invalid date: {raw}")
             expect: all 6 green

#5 result    attempt 2 · exit 0 · green 6/6
             change: src/schedule/dateparse.py +6/-4
             reading: C2 confirmed. Contract: strict ISO pre-check, calendar validation via strptime,
             ValueError on rejection; loader catches ValueError.
             refs: attempt-02.txt

#6 note      the missing fact was the loader's except clause; brief v2 was stale. Carry to feature
             decisions: rejection = ValueError, strict ISO.
```

## How It Is Recorded

- `team_attempt` writes `output/attempt-NN.txt` (full oracle output),
  `output/attempt-NN.diff` (git diff, when non-empty), and appends an `attempt`
  journal line with `cmd`, `cwd`, `exit`, `duration_s`, `timeout`, and `refs`.
  It prints `ATTEMPT: N`.
- The worker journals `result` with `team_journal --kind result --entry '{...}'
  --attempt N`; the tool merges attempt `N`'s fields into the entry (the entry
  keeps kind/seq). An unknown attempt number is refused.
- `ask` is `team_send --to mentor --kind ask`, which appends a `stuck` entry;
  the mentor's `brief` is not journaled — it lives in the mentor's session turns.
- All entries share one append-only `journal.jsonl` with increasing `seq`.

## What The Mentor Gets Out Of It

- **#2** shows the worker's full decision model: options weighed, evidence for
  each, assumptions, and the falsifiers it expects.
- **#3** shows the evidence that refuted it: exact asserts, E lines, got values,
  plus the worker's reading.
- **#4** shows the next decision with its rationale.
- **#5** shows the advice accepted and the run green.
- **#6** is the lesson that survives the chunk.

Nothing is compressed to save tokens: the mentor can correct the model, not the
symptom.
