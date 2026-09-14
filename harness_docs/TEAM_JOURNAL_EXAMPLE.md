# MiMo Worker Journal — Real-World Sample

**Captured:** 2026-09-11
**Companion to:** `TEAM_TOOL_DESIGN.md` §16 (journal design)

A full chunk of worker journaling at full depth: 3 attempts, one ask, one brief, green. The journal is worker-authored only; facts (cmd, failures, diff, trust) are attached by the tool from attempt artifacts. The ask and brief are dialogue and live in the mentor's session turns — shown between markers only to make the scenario readable. Worker prose is uncapped.

```
chunk backup-schedule/impl-3   worker: MiMo   oracle: oracle-run pytest unit/test_dateparse.py -q

#1 readback  goal: parse_date(value) -> date for strict ISO YYYY-MM-DD; ValueError otherwise;
                 load_entries skips invalid entries
             constraints: [src/schedule/dateparse.py only; tests hash-pinned; no interface changes]
             done: oracle green
             understanding: load_entries reads each entry's "date" and must skip invalid ones.
             loader.py is outside my allowlist, so I cannot see whether it detects rejection by
             exception type or by sentinel. Test names suggest both are in play:
             test_invalid_date_raises (unit) and test_loader_skips_invalid (loader).

#2 plan      attempt 1
             situation: parse_date is a stub; I need rejection semantics and a strict format check.
             options:
               A return None on invalid input
                 for: brief v2 says "reject invalid input" and names no exception;
                      test_loader_skips_invalid reads like a sentinel check
                 against: test_invalid_date_raises uses pytest.raises (line 42) — cannot pass
                          with a return value
               B raise DateParseError(Exception)
                 for: the oracle clearly expects an exception; a domain error is explicit
                 against: DateParseError appears nowhere I can see
               C raise ValueError
                 for: pytest.raises(ValueError) matches line 42 exactly; Python convention
                 against: brief v2 does not name it; cannot verify loader.py catches it
               D strict regex pre-check + C
                 for: test_reject_unpadded implies "2026-2-3" must be rejected; strptime
                      accepts it
                 against: more moving parts; I have not seen the test body yet
             choice: A
             rationale: brief v2 is this chunk's instruction; when the brief and the oracle point
             different ways the protocol says ask, not guess. Trying the literal brief first
             produces the cleanest evidence for the ask — if line 42 fails with DID NOT RAISE,
             the conflict is proven and the mentor gets a concrete question, not a hunch. Cost
             is one attempt; the benefit is a precise question.
             assumptions: load_entries skips None; invalid input arrives as str
             uncertainties: what load_entries catches or checks; whether strictness is tested
             falsifiers: line 42 red → A wrong; line 55 red → strptime too permissive
             change: wrap strptime; return None on ValueError
             expect: all 6 green if the brief reading is right; the specific bet is line 42

#3 result    attempt 1 · exit 1 · red 3/6
             cmd: (cd swarm-forge-tin/harness_tests && oracle-run python3 -m pytest persistent/unit/test_dateparse.py -q)
             failures:
               test_invalid_date_raises  unit/test_dateparse.py:42
                 assert pytest.raises(ValueError): parse_date("2026-13-40")
                 E  Failed: DID NOT RAISE <class 'ValueError'>
               test_reject_unpadded      unit/test_dateparse.py:55
                 assert parse_date("2026-2-3") raises ValueError
                 got: datetime.date(2026, 2, 3)
               test_loader_skips_invalid unit/test_loader.py:31
                 assert load_entries([{"date": "2026-13-40"}, {"date": "2026-01-02"}]) == [good]
                 got: [None, good] — None propagated, load_entries did not skip it
             change: src/schedule/dateparse.py +8/-2   (attempts/01.diff)
               - return datetime.strptime(raw, "%Y-%m-%d").date()
               + try:
               +     return datetime.strptime(raw, "%Y-%m-%d").date()
               + except ValueError:
               +     return None
             trust: tests unchanged · files = allowlist · oracle scope full
             observations:
               - line 42 red: parse_date returned None; the oracle wants an exception
               - line 31 red: load_entries does not check for None either
               - line 55 red: strptime accepts unpadded input; strictness needs a pre-check
             reading: A is refuted twice — the loader neither catches exceptions nor skips None,
             so it must rely on parse_date raising something. Line 42 pins the type to ValueError.
             B vs C stays open only because I cannot see loader.py's except clause; the loader
             test will discriminate next attempt.
             refs: attempts/01.output.txt · attempts/01.diff

#4 plan      attempt 2
             situation: A refuted. Identify what load_entries catches.
             options:
               B raise DateParseError(Exception)
                 for: discriminates the loader's except clause; line 31 green means loader catches B
                 against: new type appears nowhere; line 42 stays red because it is not a ValueError
               C raise ValueError
                 for: matches line 42; line 31 green means loader catches ValueError
                 against: if it escapes, the message looks like any other exception — less diagnostic
             choice: B
             rationale: both cost one attempt; B is the more diagnostic failure. If B fails, the
             message "DateParseError escaped load_entries" proves the loader does not catch it and
             narrows to C. If C fails, a ValueError escaping looks like any other exception — I
             learn less. Try the falsifiable one first.
             assumptions: loader has a single except clause; line 42 stays red this attempt because
             DateParseError is not a ValueError — expected, and not a refutation of B
             uncertainties: catch-by-type vs catch-by-sentinel (the latter already refuted)
             falsifiers: line 31 red with "escaped" → B wrong; line 31 green → B right
             change: add class DateParseError(Exception); raise it on invalid input
             expect: line 31 green; line 42 red (expected, not a refutation)

#5 result    attempt 2 · exit 1 · red 4/6
             failures:
               test_loader_skips_invalid unit/test_loader.py:31
                 E  DateParseError: invalid date: 2026-13-40  (escaped load_entries)
               test_invalid_date_raises  unit/test_dateparse.py:42
                 E  Failed: DID NOT RAISE <class 'ValueError'>  (DateParseError is not ValueError)
             change: src/schedule/dateparse.py +4/-2   (attempts/02.diff)
               + class DateParseError(Exception): pass
               - except ValueError: return None
               + except ValueError: raise DateParseError(raw)
             trust: tests unchanged · files = allowlist · oracle scope full
             observations:
               - line 31 red with "escaped": load_entries does not catch DateParseError
               - line 42 red because DateParseError is not a ValueError
             reading: B refuted. The loader must catch ValueError — otherwise line 42 would not
             pin it. C is the remaining hypothesis; strictness (line 55) is still unaddressed
             and will need a regex pre-check.
             refs: attempts/02.output.txt · attempts/02.diff

── dialogue (mentor session turns, not journal) ──
 ask:  loader.py is outside my allowlist. Returning None is not skipped (line 31) and
       DateParseError is not caught (line 31). Line 42 pins ValueError. Does load_entries
       catch ValueError, and does the oracle expect a specific message on invalid input?
 brief: load_entries catches ValueError and skips the entry. Brief v2 "return None" is stale —
        the oracle governs. Raise ValueError(f"invalid date: {raw}"); add the strict regex
        pre-check for "2026-2-3". One file: src/schedule/dateparse.py.
────────────────────────────────────────────────────────────────────────────────

#6 plan      attempt 3
             situation: loader contract confirmed by mentor; strictness still to fix.
             options:
               C1 raise ValueError with the raw value
                 for: satisfies line 42 and the loader's catch
                 against: line 55 (unpadded) stays red — not enough alone
               C2 raise ValueError + regex pre-check for strict ISO
                 for: fixes line 55 too; strptime still validates the calendar
                 against: one more moving part
             choice: C2
             rationale: brief confirms C, and line 55 is already red, so C1 alone cannot be green.
             ^\d{4}-\d{2}-\d{2}$ before strptime rejects unpadded input; strptime still validates
             the calendar (2026-13-40 → ValueError).
             assumptions: line 55 only checks unpadded; no other format edges in the oracle
             uncertainties: none blocking; another format test could exist unseen
             falsifiers: line 42 or 31 red again → exception type still wrong
             change: add regex pre-check; DateParseError → ValueError(f"invalid date: {raw}")
             expect: all 6 green

#7 result    attempt 3 · exit 0 · green 6/6
             cmd: (cd swarm-forge-tin/harness_tests && oracle-run python3 -m pytest persistent/unit/test_dateparse.py -q)
             change: src/schedule/dateparse.py +6/-4   (attempts/03.diff)
             trust: tests unchanged · files = allowlist · oracle scope full
             reading: C2 confirmed. Chunk contract: strict ISO pre-check, calendar validation via
             strptime, ValueError on rejection; loader catches ValueError.
             refs: attempts/03.output.txt

#8 note      the missing fact was the loader's except clause; brief v2 was stale. Carry to
             feature decisions: rejection = ValueError, strict ISO.
```

## What the mentor gets out of it

- **#2** shows the worker's full decision model: options weighed, evidence for each, the assumption that the brief governs, and the falsifiers it expects.
- **#3** shows the evidence that refuted it: exact asserts, E lines, got values, plus the worker's reading of why A died.
- **#4** shows the next decision with its rationale — why B is the more diagnostic attempt.
- **#5** shows B refuted and the hypothesis narrowed.
- **#6** shows the advice accepted and how C is shaped, strictness included.
- **#8** is the lesson that survives the chunk.

Nothing is compressed to save tokens: the mentor can correct the model, not the symptom.
