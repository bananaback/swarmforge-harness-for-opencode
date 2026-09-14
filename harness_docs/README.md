# Harness Docs

Index and status snapshot. Read this first in a new session, then `ROADMAP.md` for the
milestone tracker.

**Updated:** 2026-09-15 · **Working tree:** uncommitted (M5 mentor-only advisory pair complete;
see `ROADMAP.md`)

## Where We Are

- The harness points at itself: `swarm-forge-tin/harness.json` sets
  `workspace_root = ".."` and `source_roots = ["tools"]`.
- The wiring seam is implemented and tool-native: `harness.json` + `tools/wiring.py` +
  `.opencode/lib/wiring.ts` + `tools/harness` CLI (`config` / `status` / `clean`).
- **M2 state layout:** live work is grouped under
  `<state_root>/tasks/<UTC-date>/<task>/<NN>-<role>/{input,journal.jsonl,output}` with a
  `done/` mirror. Journals are append-only; inputs are write-once.
- **M2 deterministic payloads:** `team_context` serves the coder a fixed 11-section payload
  (TASK, DEFINITION OF DONE, RESOLVED PATHS, INPUTS, FEATURE, INTERFACE CONTRACT, FILES, HOW
  TO RUN, PRIOR ATTEMPT, WHEN STUCK, WHEN DONE) and the mentor a system prompt + GOAL, RULES,
  TRAIL, ASK, FAILURE — both assembled from `task.json` + `harness.json` with no path
  discovery.
- The self-hosted persistent-test root is chosen by config kind (`harness` when the config
  belongs to the pack, else `project`), without stat-ing configured paths.
- Test areas are split: `harness_tests/persistent/` (self-tests),
  `project_tests/persistent/` (src-project, pack-side), `hot_tests/` (shared generated).
- The acceptance pipeline is self-hosted: 4 features (`harness_wiring`, `task_state_layout`,
  `deterministic_coder_payload`, `deterministic_mentor_payload`) parse into `dump/`, generate
  into `hot_tests/acceptance/`, and run green.
- **M3 spec mutation:** generated entry points honor `SWARM_ACCEPTANCE_IR`, so one generated
  file evaluates every mutant. `acceptance/mutation_runner.py` is the persistent worker
  adapter; `acceptance/run_mutation.py` copies each feature to `hot_tests/mutation/`, drives
  `<pack>/tools/gherkin-mutator`, and writes `dump/mutation/<stem>.json`. Authored features
  are never touched. Self-hosted coder-feature run: 36 mutants, 28 killed, 8 survived, 0
  errors.
- **M4 TS bridge coverage:** `persistent/tools/ts/wiring.test.ts` (16 `node:test` cases) pins
  `findConfig`/`loadWiring`/`seatForAgent`/`parseReady`/`messageText` under Node type
  stripping; `ts-resolve.mjs` supplies the extensionless-import hook. `autobind_probe.ts` +
  `test_ts_wiring.py` assert a real `TEAM_WAITING` spawn binds before the first `team_pull`
  (`status --ready` → `queued`; pull → `RESUMED`). `runTeam` now uses
  `node:child_process`, so the autobind core runs outside Bun.
- **M5 mentor-only advisory pair:** the senior tier is gone from the seat graph, the
  `SEATS`/`ROLES`/`EDGES` tables, the autobind map, and the agent roster. Worker and mentor
  talk freely — no ask cap and no attempt cap; the mentor owns boundary calls directly.
- All 6 roles run `opencode-go/deepseek-v4.1-flash` variant `high`.

**Self-hosted verification:** persistent suite 175 passed (includes 12 property); 59
acceptance scenarios pass; ruff clean; CRAP 0 functions above 10; DRY 0 clones.

## Doc Index

| File | Purpose | Status |
|---|---|---|
| `ROADMAP.md` | Milestone tracker: status, scope, exit criteria, backlog, resume checklist | current |
| `HARNESS_WIRING.md` | Wiring design, config schema, resolution order, deliverables, next | current |
| `PROJECT_STRUCTURE.md` | Full tree, config, tooling quick reference, verification status | current |
| `TEST_PERSISTENCE_POLICY.md` | Which test artifacts persist vs regenerate | current |
| `TEAM_TOOL_DESIGN.md` | Team chunk/seat tool design (mail/team routing) | current (paths via wiring) |
| `WORKFLOW_ROUTING.md` | Model tiers and role→model routing | current |
| `TEAM_JOURNAL_EXAMPLE.md` | Sample worker journal (attempts, ask, brief) | reference |
| `prompting-guide.md` | General prompting notes | reference (not part of the pack) |
| `CONVERSION.md` | Conversion history; do not read per AGENTS.md | historical |

## Done

1. Cleanup: removed the old `src/` experiment, its tests, `tmp/`, root HTML reports.
2. Docs moved to `harness_docs/`; test structure organized into persistent vs hot.
3. Wiring implemented: config, Python + TS resolvers, per-tool artifact/state routing,
   `harness` CLI with guarded `clean`.
4. Prompts updated to the wiring model.
5. Self-hosting run: Gherkin feature + acceptance pipeline + unit/property/tool tests.
6. M1: hardened `mailbox.py`/`team.py` with behavior tests (process-group kill fix, CRAP 0).
7. **M2 context-engineering (complete):**
   - `task_state_layout.feature` (10 scenarios): dated task/chunk layout, write-once inputs,
     append-only journal kinds, `close --preserve`/delete with empty-date-folder cleanup.
   - `deterministic_coder_payload.feature` (5 scenarios): 11-section coder payload from
     `task.json` + `harness.json`.
   - `deterministic_mentor_payload.feature` (7 scenarios): system prompt + GOAL/RULES/TRAIL/
     ASK/FAILURE with verbatim failure evidence.
   - Self-host root fix: payloads name `harness_tests/persistent` when config belongs to the
     pack, a wired project's root otherwise.
   - Orchestrator hot-fixes: `team.py` `pull`/`context` deliver `input/`; `.opencode/tools/
     team.ts` uses `open <task> --role`.
   - Model routing: all roles on `deepseek-v4.1-flash` `high`.
8. **M3 spec mutation (complete):**
   - `generator.py` IR override seam (`SWARM_ACCEPTANCE_IR`) so one generated entry point
     evaluates every mutant.
   - `acceptance/mutation_runner.py` — persistent worker adapter implementing the
     `mutator-spec.md` newline-delimited JSON protocol.
   - `acceptance/run_mutation.py` — one command that copies features to `hot_tests/mutation/`,
     generates entry points, runs `gherkin-mutator`, and reports under `dump/mutation/`.
   - `tools/test_mutation_runner.py` (13 tests), including a fast real-mutator probe.
9. **M4 TS bridge coverage (complete):**
   - `tools/ts/wiring.test.ts` (16 `node:test` cases) for `findConfig`/`loadWiring`/
     `seatForAgent`/`parseReady`/`messageText`/`autoBindPendingSeat` skip paths.
   - `tools/ts/ts-resolve.mjs` — Node resolve hook for the pack's extensionless `.ts` imports.
   - `tools/ts/autobind_probe.ts` + `tools/test_ts_wiring.py` — real bind-before-first-pull
     probe; `runTeam` moved to `node:child_process` so the core runs outside Bun.
10. **M5 mentor-only advisory pair (complete):**
    - Removed the `senior` seat from `team.py` (`SEATS`/`ROLES`/`EDGES`), `wiring.py`,
      `harness.json`, `.opencode/lib/team-autobind.ts`, `.opencode/tools/team.ts`, and the
      agent roster (`senior.md` deleted; orchestrator/mentor/coder/refactorer/architect updated).
    - Removed ask and attempt caps: `WHEN_STUCK_POLICY` now says "no attempt cap / ask again
      after each brief"; the worker and mentor talk freely until the oracle is green.

## Next

- M5 (done): senior tier removed; mentor-only advisory pair with free ask/brief and no caps.
- M6: fill `project_tests/` on a wired project via `SWARM_CONFIG`.
- Commit the current work when directed; nothing is committed.

## Switching Projects

- Same pack, other project: `SWARM_CONFIG=/path/to/project/harness.json`, or edit
  `workspace_root` in `swarm-forge-tin/harness.json`.
- Before switching: `swarm-forge-tin/tools/harness clean all` (or `hot`, `state`,
  `artifacts` individually). `clean state` refuses while mail/team items are in process
  unless `--force`.
