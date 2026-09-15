# SwarmForge Roadmap

The resume point for a new session: read this, then [README.md](README.md) for the
map and `AGENTS.md` for the constitution.

**Updated:** 2026-09-15

## How To Use

- A milestone is **Done** only when its exit criteria pass; update the table and
  the note in the same change.
- Keep at most one milestone `In progress`.
- Run constitution tools one at a time ([verification](#verification)).

## Status

| # | Milestone | Status | Exit criteria (short) |
|---|---|---|---|
| M1 | Harden mail + team with behavior tests | **Done** | tests green, acceptance green, ruff/CRAP/DRY clean |
| M2 | Context-engineering redesign | **Done** | dated task/chunk layout + deterministic coder/mentor payloads |
| M3 | Wire `gherkin-mutator` → `hot_tests/mutation` | **Done** | mutation run + report under artifacts/hot |
| M4 | TS resolver + autobind automation | **Done** | `.opencode/lib/wiring.ts` covered; autobind probe |
| M5 | Mentor-only advisory pair (senior removed, no caps) | **Done** | senior gone; free ask/brief; gates green |
| M6 | Sample-project validation | Backlog | committed sample projects green through the full pipeline |
| M7 | Prompt engineering for all six agents | **Done** | every agent prompt revised; suite and acceptance green |
| M8 | Add OOP/SOLID designer and task-breaker agents | **Done** | two prompts; task-breaker output feeds `team_open`; gates green |
| M9 | Validate the design + execution branches together | **Done** | one feature runs both branches with no manual glue |
| M10 | Tool + durable-state correctness audit | Backlog | contracts and invariants proven; known limitations resolved |

## Current State

Self-hosting and green. The pack points at this repository; all eight agents run
`opencode-go/deepseek-v4.1-flash` variant `high`.

**This is a working baseline, not a production-ready harness.** Two reliability
questions are still open and gate adoption:

1. **Tool and state correctness** — each tool and the durable state are tested on
   happy paths and their documented contracts, not under stress, concurrency, or
   crash recovery.
2. **Wiring portability** — the pack is proven only self-hosting; no committed
   sample project exercises it end to end.

M9 (branch compatibility) is done at the tool level: a deterministic integration
run drives both branches through the real CLIs on a scratch project with no
manual glue, and its one real seam defect (nested phase chunks invisible to
`status --ready`) is fixed. See
[M9-VALIDATION.md](M9-VALIDATION.md). M10 and M6 (in that order) remain; do not
treat the harness as production-ready until they pass.

- Wiring: `harness.json` + `tools/wiring.py` + `.opencode/lib/wiring.ts` +
  `tools/harness` (`config` / `status` / `clean`).
- State: `tasks/<UTC-date>/<task>/<NN-role>/{input,journal.jsonl,output}` with a
  `done/` mirror; write-once inputs, append-only journals.
- Tools: `mailbox.py` (durable mail), `team.py` (seat routing, journal, oracle
  attempts, deterministic context payloads), and `taskbreak.py` (task-breaker
  plan → `team_open` seeds).
- Acceptance: 4 features, 28 scenarios, 59 executions green.
- Quality: 191 persistent tests; ruff clean; CRAP 0 functions above 10 (scoped);
  DRY 0 clones. Mutation (coder feature): 36 mutants / 28 killed / 8 survived /
  0 errors.
- Validation: M9 branch integration run — 51 recorded tool calls, every exit 0,
  ending drained (`READY: none`, no queued/in-process mail); run log at
  `dump/m9/runlog.json`; friction in [M9-VALIDATION.md](M9-VALIDATION.md).
- Design: the `designer` and `task-breaker` prompts are the out-of-band design
  pre-phase (M8). The designer writes the design seed; the task-breaker writes a
  conflict-free chunk plan, and `taskbreak.py` opens each chunk with no hand
  translation.
- Prompts: all eight agent prompts written against the current tool surface —
  goal/anti-goal headers, XML reasoning scaffolds, and contrastive handoff/brief
  examples; stale sealed/senior/cap wording removed.

## Next

The reliability program: prove the baseline before production use. M9 validated
the branch seams; M10 now hardens the tools and durable state.

- **M9 — Validate the design and execution branches together (done).** Both
  branches ran on one scratch feature with no manual glue:
  `specifier → designer → task-breaker → coder → refactorer → architect`,
  51 tool calls, every seam asserted, ending drained. The one real defect it
  surfaced — nested phase chunks (`cart/refactorer`) invisible to
  `team status --ready`, which forced the manual `team_bind` fallback — is
  fixed. Evidence and friction list: [M9-VALIDATION.md](M9-VALIDATION.md);
  run log: `dump/m9/runlog.json`. Persistent suite and acceptance green.

- **M10 — Tool and durable-state correctness audit (backlog, next).** Goal: prove each
  tool's contract and the state machine beyond the happy path, not just cover
  them. Scope:
  - contract audit of `mailbox`, `team`, `taskbreak`, `harness`, and `wiring`:
    every command's invariants, refusals, exit codes, and ownership rules;
  - state invariants: write-once inputs, append-only journals, single-owner
    claims, atomic writes, lock coverage, `clean`/`--force` safety;
  - stress and recovery: property/fuzz tests plus duplicate dispatch,
    interrupted `mail_pull`/`team_done`, lock contention, corrupt JSON, and the
    midnight date boundary;
  - resolve or explicitly accept every entry in
    [ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations).
  Exit criteria: each limitation fixed or accepted with a one-line rationale;
  property and crash-recovery tests green; no data-loss path found; CRAP/DRY
  clean.

- **M6 — Validate against committed sample projects (backlog).** Goal: prove the
  pack runs against a project other than itself, using committed sample projects
  rather than an arbitrary external one, so the check is deterministic and
  repeatable. Create one or more small, self-contained sample projects -- each
  with its own `harness.json`, source root, test roots, and features -- and run
  the whole pipeline and quality tools against them via `--config` /
  `SWARM_CONFIG`. Scope:
  - keep each sample committed as a fixture so the run repeats in the suite;
  - fill its test root (`project_tests/persistent/{unit,property,features,acceptance}`
    or the sample's own root) and drive a feature through the pipeline;
  - verify persistent-root `kind` selection and artifacts/hot/features resolution;
  - check multi-project `harness clean all` isolation;
  - confirm nothing is written outside the sample's configured roots and no pack
    path is hardcoded.
  Exit criteria: every sample project completes the pipeline with its tests and
  acceptance green; the samples double as integration fixtures; onboarding steps
  documented.

## Decided (Do Not Re-litigate)

- **All roles use v4.1 `high`.** Changing a model or agent config needs an opencode
  restart.
- **No senior tier; no ask or attempt caps.** The pair talk until the oracle is
  green; the mentor owns boundary calls directly.
- **Plan-time routing** (`v4-led` / `v4.1-led` chunks) is deferred.
- **Rejected alternatives:** message content in the wake line; pre-spawning the
  mentor; rollback checkpoints; epochs/fencing tokens; a long-lived mentor; a
  model holding session ids; role-name routing for the pair.

## Backlog / Known Gaps

M10 owns resolving or explicitly accepting these; tracked in
[ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations):

- `sealed` is never set; `team.py` still carries the field and its `task is
  sealed` guards, which are dead paths.
- `bind`/`close` resolve under today's UTC date; a task opened before midnight
  cannot be bound/closed after.
- `harness clean state`'s in-process check still uses the old `team/**/seats/*`
  glob, so it counts mail but not team items.
- The TS `findConfig` has no CWD walk-up and no pack-root fallback (latent).

## Verification

Run from the repository root, one tool at a time:

```bash
# persistent tests (191; unit 17, property 12, tools 162)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q

# M9 branch integration (both branches, one feature)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  persistent/tools/test_branch_integration.py -q

# property only (12)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/property -q

# TS bridges: node:test suite + autobind bind-before-first-pull probe
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools/test_ts_wiring.py -q

# acceptance (parse -> dry -> generate -> run; 59 executions)
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py

# spec mutation (standalone; report under dump/mutation, work under hot_tests/mutation)
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_mutation.py --feature swarm-forge-tin/harness_tests/persistent/features/deterministic_coder_payload.feature

# lint
swarm-forge-tin/tools/ruff4py swarm-forge-tin/tools swarm-forge-tin/harness_tests/persistent

# complexity/coverage for the communication tools
swarm-forge-tin/tools/crap4py --source-root swarm-forge-tin/tools \
  --test-path swarm-forge-tin/harness_tests/persistent \
  team.py mailbox.py taskbreak.py wiring.py

# duplication
swarm-forge-tin/tools/dry4py --min-lines 4 swarm-forge-tin/tools

# resolved paths
swarm-forge-tin/tools/harness status
```

## Resume Checklist

1. `git status` and `git diff --stat` — confirm a clean or understood tree.
2. Restart opencode if an agent/model config changed; then run the persistent
   suite and the acceptance pipeline. Both must be green before new work (191 /
   59).
3. Pick the next milestone; move it to `In progress` here.
4. Follow TDD: failing behavior test first, smallest change, then the gates.
5. Record the milestone's evidence here and in [README.md](README.md) before
   handoff.
