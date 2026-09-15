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
| M6 | Fill `project_tests/` on a wired project | Backlog | project config green end to end |
| M7 | Prompt engineering for all six agents | **Done** | every agent prompt revised; suite and acceptance green |

## Current State

Self-hosting and green. The pack points at this repository; all six agents run
`opencode-go/deepseek-v4.1-flash` variant `high`.

- Wiring: `harness.json` + `tools/wiring.py` + `.opencode/lib/wiring.ts` +
  `tools/harness` (`config` / `status` / `clean`).
- State: `tasks/<UTC-date>/<task>/<NN-role>/{input,journal.jsonl,output}` with a
  `done/` mirror; write-once inputs, append-only journals.
- Tools: `mailbox.py` (durable mail) and `team.py` (seat routing, journal, oracle
  attempts, deterministic context payloads).
- Acceptance: 4 features, 28 scenarios, 59 executions green.
- Quality: 175 persistent tests; ruff clean; CRAP 0 functions above 10; DRY 0
  clones. Mutation (coder feature): 36 mutants / 28 killed / 8 survived / 0
  errors.
- Prompts: all six agent prompts revised against the current tool surface —
  goal/anti-goal headers, XML reasoning scaffolds, and contrastive handoff/brief
  examples; stale sealed/senior/cap wording removed.

## Next

- **M6 — Fill `project_tests/` on a wired project (backlog).** Prove the pack
  against a real project via `SWARM_CONFIG=/path/to/project/harness.json`. Scope:
  fill `project_tests/persistent/{unit,property,features,acceptance}` and run the
  acceptance pipeline against the project source roots.

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

Tracked in [ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations):

- `sealed` is never set; `team.py` still carries the field and its `task is
  sealed` guards, which are dead paths.
- `team status` / `--ready` only scan one level, so nested task ids cannot
  auto-bind; prefer flat chunk names.
- `bind`/`close` resolve under today's UTC date; a task opened before midnight
  cannot be bound/closed after.
- `harness clean state`'s in-process check still uses the old `team/**/seats/*`
  glob, so it counts mail but not team items.
- The TS `findConfig` has no CWD walk-up and no pack-root fallback (latent).

## Verification

Run from the repository root, one tool at a time:

```bash
# persistent tests (175; unit 17, property 12, tools 146)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q

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
  --test-path swarm-forge-tin/harness_tests/persistent team.py mailbox.py

# duplication
swarm-forge-tin/tools/dry4py --min-lines 4 swarm-forge-tin/tools

# resolved paths
swarm-forge-tin/tools/harness status
```

## Resume Checklist

1. `git status` and `git diff --stat` — confirm a clean or understood tree.
2. Restart opencode if an agent/model config changed; then run the persistent
   suite and the acceptance pipeline. Both must be green before new work (175 /
   59).
3. Pick the next milestone; move it to `In progress` here.
4. Follow TDD: failing behavior test first, smallest change, then the gates.
5. Record the milestone's evidence here and in [README.md](README.md) before
   handoff.
