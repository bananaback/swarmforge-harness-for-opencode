# M9 Validation — Design Branch + Execution Branch

The milestone's validation run: prove the design pair
(`designer → task-breaker`) and the execution chain
(`specifier → coder → refactorer → architect`) converge on one feature with no
manual glue. The machine-readable run log lives at
`swarm-forge-tin/dump/m9/runlog.json` (disposable, rebuilt by the command
below); this file is the committed evidence and friction list.

The run is a deterministic integration test, not a live eight-agent dispatch:
it drives the real `mailbox.py`, `team.py`, and `taskbreak.py` CLIs through the
documented role sequence on a scratch project. It runs in the persistent suite,
so the seams stay proven on every change.

## Reproduce

```bash
# full run + suite
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  persistent/tools/test_branch_integration.py -q

# capture the run log under the artifacts root
cd swarm-forge-tin/harness_tests && \
  SWARM_E2E_RUNLOG="$PWD/../dump/m9/runlog.json" \
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  persistent/tools/test_branch_integration.py::test_design_and_execution_branches_converge -q
```

## What Ran

A scratch project (`harness.json` with its own `state/`, `artifacts/`, `tests/`,
`src/`, `features/`) plus a real `cart.feature`. The run is 51 recorded tool
calls, every one exit `0`:

| Phase | Actor | Calls | Outcome |
|---|---|---:|---|
| Execution | orchestrator → specifier | 5 | handoff pulled; `gherkin-parser` writes `artifacts/cart.json`; handoff to coder; done |
| Design | orchestrator → designer | 4 | handoff pulled; seed written to `features/design/cart.md`; handoff to task-breaker; done |
| Design | task-breaker | 2 | reads the seed; writes `artifacts/taskbreak/cart.plan.json`; sends no chain mail |
| Open | orchestrator → `taskbreak.py` | 1 | opens chunk `cart` from the plan |
| Execution | coder chunk | 16 | pull → mail pull → context (design in payload) → journal → oracle green → ask/brief → forward handoff → done → close |
| Execution | refactorer chunk | 12 | nested id `cart/refactorer`; pull → mail from coder → oracle → handoff → done → close |
| Execution | architect chunk | 9 | nested id `cart/architect`; pull → mail from refactorer → oracle → done → close |
| Drain | orchestrator | 2 | `team status --ready` = `READY: none`; no queued or in-process mail |

## Seams Verified

| Seam (ROADMAP) | Evidence in the run |
|---|---|
| designer seed readable by task-breaker | task-breaker asserts `features/design/cart.md` exists before writing the plan |
| designer seed readable by `team_open` | plan references `features/design/cart.md`; `taskbreak` copies it; coder `input/` holds it byte-for-byte |
| `taskbreak.py` opens each planned chunk | `OPENED: cart`; task `cart/01-coder` created |
| coder chunk receives the specifier mail | coder mailbox pull prints `TASK_NAME: cart` and `FROM: specifier` |
| coder chunk receives the design seed | coder 11-section payload carries `INTERFACE CONTRACT` with `class Cart` |
| forward handoffs | coder → refactorer and refactorer → architect mail pulled by the next role |
| `team_close` | each phase chunk closed; live task tree pruned |
| `team_status --ready` drains | after the architect chunk, `READY: none` |
| ask/brief recovery | worker `ask` recorded as `stuck`; mentor `brief` returns; mentor payload `ASK` shows the question |
| interrupted pull | second `team_pull` on the bound session prints `RESUMED: yes` with the same item |
| unbound session | `team_pull` on an unbound session exits `2` with `not bound to any team seat` |
| red attempt | a failing oracle records `EXIT: 3`; the journal `result --attempt 1` carries `exit: 3` |

## Friction Found

1. **Nested phase-chunk ids were invisible to `team status --ready` — FIXED.**
   A phase chunk is named `<feature>/<role>` (`cart/refactorer`,
   `cart/architect`), but `task_docs` scanned one level under the date folder
   and read only `<date>/<task>/task.json`, never `<date>/cart/refactorer/…`.
   `status --ready` printed `READY: none`, so the autobind plugin could not bind
   the refactorer/architect worker seat and the documented flow silently needed
   the manual `team_bind` fallback — the exact "manual glue" M9 set out to
   remove. `task_docs` now recurses (`rglob("task.json")`), so nested chunks
   appear in `status`/`--ready`. Covered by
   `test_status_ready_sees_nested_phase_chunk` and the end-to-end run.

2. **`team_pull` always reports `RESUMED: yes` after an explicit `team_bind` —
   accepted.** The dispatch order binds the seat (`team_bind` or autobind)
   before the first pull, and `cmd_pull` treats an already-bound session as a
   resume. Harmless, but it makes a first pull and a resumed pull
   indistinguishable in the CLI output; the run asserts on the item identity
   instead. No action.

3. **Phase-chunk opening is duplicated between `taskbreak.py` and `team_open` —
   accepted.** `taskbreak.py` opens the planned (coder) chunks, while the
   orchestrator opens the later refactorer/architect chunks with `team_open`,
   passing the same feature/design again. This is the documented split (the
   plan covers the coder phase); noting it so a future plan schema can carry
   all phases if that is wanted.

4. **Deferred to M10 (not hit by this run).** `sealed` is never set;
   `bind`/`close` resolve under today's UTC date (midnight boundary);
   `harness clean state`'s in-process check still uses the old team glob; the
   TS `findConfig` lacks a CWD walk-up. These are unchanged by M9 and remain in
   [ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations).

## Scope Notes

- The scratch feature is a single coder chunk, so parallel multi-chunk
  decomposition was not exercised end to end; `taskbreak` opening several chunks
  is unit-covered by `test_plan_opens_one_chunk_per_entry`.
- The run uses `team_bind` explicitly to model what the `team-autobind` plugin
  does at dispatch; the plugin itself is covered by the TS probe.
