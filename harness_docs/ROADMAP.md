# SwarmForge Roadmap

Durable milestone tracker. This is the resume point for a new session: read this, then
`harness_docs/README.md` for the status snapshot, then `AGENTS.md` for rules.

**Updated:** 2026-09-15 · **Working tree:** uncommitted (see [Working Tree](#working-tree))

## How To Use

- A milestone is **Done** only when its exit criteria all pass; update the table and the
  detail block in the same commit.
- Keep one milestone `In progress` at a time.
- Ideas from `harness_docs/context_engineering/` and the other drafts are **first draft, not
  ground truth**; re-derive behavior from tests and `harness.json`.
- Verification commands live in [Verification](#verification). Run constitution tools one at
  a time.

## Status

| # | Milestone | Status | Exit criteria (short) |
|---|---|---|---|
| M1 | Harden mail + team with behavior tests | **Done** | tests green, acceptance green, ruff/CRAP/DRY clean |
| M2 | Context-engineering redesign | **Done** | dated task/chunk layout + deterministic coder/mentor payloads; gates green |
| M3 | Wire `gherkin-mutator` → `hot_tests/mutation` | **Done** | mutation run + report under artifacts/hot |
| M4 | TS resolver + autobind automation | **Done** | `.opencode/lib/wiring.ts` covered; autobind probe |
| M5 | Mentor-only advisory pair (senior removed, no caps) | **Done** | senior gone; free ask/brief; gates green |
| M6 | Fill `project_tests/` on a wired project | Backlog | project config green end to end |

---

## M1 — Harden mail + team with behavior tests — Done (2026-09-14)

**Goal.** Make the two load-bearing communication tools trustworthy: pin their contract
with tests, fix everything the tests surface.

**Delivered**
- `team.py` — process-group kill fix: `team_attempt --timeout` now kills the oracle's whole
  process group, not just the shell.
- `mailbox.py` — behavior-preserving split of `validate_send`, `cmd_pull`, `cmd_done`,
  `cmd_status` into single-job helpers.
- Tests under `harness_tests/persistent/`: `tools/test_mailbox_behavior.py`,
  `tools/test_team_behavior.py`, `tools/test_tool_units.py`, `unit/test_wiring.py`, `support.py`.
- Docs reconciled to v4.1 `high`.

---

## M2 — Context-engineering redesign — Done (2026-09-15)

**Goal.** Replace ad-hoc context with tool-assembled, deterministic payloads, and group state
by task/chunk so a resumed session reads durable history instead of re-discovering.

**Delivered (three verified feature slices + one follow-up fix)**
- `features/task_state_layout.feature` (10 scenarios) — live work under
  `<state_root>/tasks/<UTC-date>/<task>/<NN>-<role>/{input,journal.jsonl,output}` with a
  `done/` mirror; write-once `input/`; append-only journal with tool kinds
  (`open/attempt/stuck/advice/done`) and worker kinds (`readback/plan/result/note`); unknown
  kinds refused; `close --preserve` moves a task whole, delete cleans exactly that task and
  prunes an emptied date folder.
- `features/deterministic_coder_payload.feature` (5 scenarios) — `team_context` full mode for a
  coder emits exactly 11 fixed sections in order, sourced from `task.json` + `harness.json`;
  RESOLVED PATHS reports configured paths verbatim without touching disk; payload is stable
  across calls.
- `features/deterministic_mentor_payload.feature` (7 scenarios) — `team_context` for the mentor
  seat emits a system prompt + GOAL, RULES, TRAIL, ASK, FAILURE, with worker-only ordered
  TRAIL and verbatim failure evidence; no model call.
- Follow-up fix (architect-found): `persistent_test_root` selects by config kind —
  `harness_tests/persistent` for a self-hosted pack, the project root for a wired project —
  without stat-ing configured paths.
- Orchestrator seam hot-fixes (operator-authorized):
  - `team.py` `pull`/`context` deliver the write-once `input/` files again.
  - `.opencode/tools/team.ts` updated to the new `open <task> --role` CLI.
- Model routing: all 7 roles on `opencode-go/deepseek-v4.1-flash` variant `high`.
- Tests: migrated `tools/test_team_behavior.py`, `tools/test_state_routing.py`,
  `tools/test_tool_units.py`; added `tools/test_coder_payload.py`,
  `tools/test_mentor_payload.py`, `property/test_team_properties.py`; acceptance step handlers
  for all three features in `persistent/acceptance/steps.py`.

**Evidence.** 159 persistent tests pass (includes 12 property); 59 acceptance scenarios pass
across 4 features; `ruff4py` clean on `tools` + `harness_tests/persistent`; CRAP 0 functions
above 10 for `team.py`/`mailbox.py`; DRY 0 clones. Each slice was verified independently by the
architect (ruff, DRY, persistent, property, acceptance, oracle).

**Notes / open items**
- The team CLI changed shape: `open <task> --role <role> [--brief/--feature/--design]`,
  `close <task> [--preserve]`, and state lives under `<state>/tasks/` now; the old
  `<state>/team/<chunk>` layout is gone. One orphaned old-layout dir remains at
  `<state>/team/task_state_layout/` (pre-migration chunk); it is inert and safe to delete
  when cleaning state. Live: no tasks; `done/` holds the preserved
  `task_state_layout-refactorer`; mailbox drained.
- Phase team tasks use **flat** names (e.g. `task_state_layout-refactorer`): `team.py status`
  only scans one level under `tasks/`, so nested `<feature>/<role>` task names are invisible to
  `status --ready` (latent; candidate follow-up).
- `cmd_bind`/`cmd_close` resolve the task under **today's** UTC date, so a task opened before
  midnight cannot be bound/closed (architect observation; latent, outside the feature contract).
- The `team-autobind` plugin maps agents to the `worker/mentor` seats; it binds on
  `status --ready` `worker SPAWN_PENDING`.
- Docs `PROJECT_STRUCTURE.md`, `HARNESS_WIRING.md`, `TEST_PERSISTENCE_POLICY.md` may still quote
  M1 counts; refresh when convenient.

---

## M3 — Wire `gherkin-mutator` → `hot_tests/mutation` — Done (2026-09-15)

**Goal.** Spec quality verified by mutation, not only parse + dry-check.

**Delivered**
- `generator.py` IR override seam: generated entry points load `SWARM_ACCEPTANCE_IR`
  when set, so one generated file evaluates every mutant (the mutator's required model).
  The base IR is still embedded and deterministic.
- `acceptance/mutation_runner.py` — persistent worker adapter for `gherkin-mutator`:
  newline-delimited JSON protocol, pytest exit-code classification (`0` → success,
  `1` → killed, else infrastructure error), protocol data on stdout only.
- `acceptance/run_mutation.py` — the one command: copies each feature into
  `hot_tests/mutation/<stem>/features/`, parses + generates entry points once, then runs
  `<pack>/tools/gherkin-mutator` and writes `<artifacts_root>/mutation/<stem>.json`.
  Authored features are never touched; the mutator's stamp/manifest lands only on the
  disposable copy.
- `tools/test_mutation_runner.py` — 13 tool tests: classification, worker protocol, IR
  override, orchestrator wiring + exit code, and one fast real-mutator probe.

**Evidence.** 172 persistent tests pass (was 159; +13); 59 acceptance scenarios pass
across 4 features; `ruff4py` clean on `tools` + `harness_tests/persistent`; CRAP 0
functions above 10 for `team.py`/`mailbox.py`; DRY 0 clones. Self-hosted full mutation run
on `deterministic_coder_payload.feature`: total=36 killed=28 survived=8 errors=0, report at
`dump/mutation/deterministic_coder_payload.json`.

**Command.**

```text
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_mutation.py \
  [--feature <feature>] [--level full|hard|soft]
```

Default mutates every configured feature and reports per feature; exits `1` when any
mutation survives or errors. The eight survivors are oracle gaps (values the scenario
asserts against themselves, e.g. resolved-path locations), not wiring failures.

**Notes / open items**
- Full self-hosted run is slow (~4 min for the 36-mutant coder feature) because each
  mutant spawns the harness step handlers; it is a standalone command, not part of the
  persistent suite. The suite covers the runner with a 1-mutant real-mutator probe instead.
- `--level hard` never reuses manifests here: the runner re-copies the feature each run, so
  the disposable copy starts clean. Differential reuse remains available when the mutator is
  pointed at a persistent feature copy.

---

## M4 — TS resolver + autobind automation — Done (2026-09-15)

**Goal.** Cover the opencode TS bridges automatically and turn the one-off autobind timing
probe into an assertion.

**Delivered**
- `.opencode/lib/team-autobind.ts` — `runTeam` now uses `node:child_process.spawnSync`
  (portable to both Bun and Node) instead of `Bun.spawnSync`, so the auto-bind core is
  loadable and probeable outside opencode.
- `persistent/tools/ts/wiring.test.ts` — 16 `node:test` cases for `findConfig`
  (`SWARM_CONFIG`/walk-up/nested pack/`SWARM_PACK`/none), `loadWiring` (relative expansion,
  defaults, `SWARM_*` overrides, missing pack), `seatForAgent`, `parseReady`, `messageText`,
  and the `autoBindPendingSeat` skip paths (including a real `team.py status --ready` call).
- `persistent/tools/ts/ts-resolve.mjs` — Node resolve hook that retries extensionless
  relative imports with a `.ts` suffix, so the pack's TypeScript-style imports load
  unmodified under Node's type stripping.
- `persistent/tools/ts/autobind_probe.ts` — CLI entry that runs the real
  `autoBindPendingSeat` for a given directory/session/agent and prints JSON.
- `persistent/tools/test_ts_wiring.py` — pytest wrapper: runs the TS suite, and an
  end-to-end probe that opens a real phase chunk, proves an unbound session's `pull` is
  refused, runs `autoBindPendingSeat`, then asserts `status --ready` is `queued` and the
  first `pull` returns `RESUMED: yes` (bound before the first pull).

**Evidence.** 174 persistent tests pass (was 172; +2 wrappers running the 16-case TS suite);
59 acceptance scenarios pass across 4 features; `ruff4py` clean; CRAP 0 functions above 10
for `team.py`/`mailbox.py`; DRY 0 clones.

**Command.**

```text
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools/test_ts_wiring.py -q
```

**Notes / open items**
- The TS suite needs `node` (v22.6+ for type stripping; this repo uses v24) and is skipped
  when `node` is absent. It does not cover `team.ts`/`mail.ts` tool registrations, which are
  exercised only through live opencode dispatch.
- `findConfig` (TS) still differs from Python `find_config`: with no `start` it does not walk
  up from CWD, and it has no `PACK_ROOT` fallback (bridges always pass a start, so this is
  latent).

---

## M5 — Mentor-only advisory pair (senior removed, no caps) — Done (2026-09-15)

**Goal.** Drop the senior escalation tier as redundant and remove the ask/attempt caps so the
worker and mentor talk until the chunk is green.

**Delivered**
- Seat graph reduced to `worker` + `mentor`: `team.py` `SEATS`/`ROLES`/`EDGES`, `wiring.py`
  `DEFAULT_ROLES`, `harness.json` `roles`, `.opencode/lib/team-autobind.ts` `Seat`/map, and
  `.opencode/tools/team.ts` enums now admit no `senior` seat and no `escalate`/`decision` kinds.
- Caps removed: `WHEN_STUCK_POLICY` no longer stops on a repeated signature or a fixed attempt
  count; it keeps the oracle loop running and tells the worker to ask again after each brief.
  The mentor owns boundary calls directly (no escalation).
- Roster/prompt updates: `senior.md` deleted; orchestrator/mentor/coder/refactorer/architect
  prompts describe the pair and the free dialogue.
- Tests: `tools/test_team_behavior.py` (senior refused; repeated ask/brief),
  `tools/test_tool_units.py` (`senior` rejected as a seat), `tools/ts/wiring.test.ts`
  (`seatForAgent("senior")` → null).

**Evidence.** 175 persistent tests pass (was 174; +1); 59 acceptance scenarios pass; gates run
per the Verification section.

**Notes / open items**
- Decided: no budget locus (no ask or attempt caps) and no mentor takeover; the mentor stays
  advisory-only. This closes `TEAM_TOOL_DESIGN.md` §14 and `WORKFLOW_ROUTING.md` §5.

## M6 — Fill `project_tests/` on a wired project — Backlog

**Goal.** Prove the pack on a real project via `SWARM_CONFIG=/path/to/project/harness.json`.
**Scope.** Fill `project_tests/persistent/{unit,property,features,acceptance}`; run the
acceptance pipeline against the project source roots.

---

## Deferred / Decided

- **Reasoning roles = v4.1 `high`.** All 6 roles now use `opencode-go/deepseek-v4.1-flash`
  variant `high` (restart required to load agent configs).
- **No senior tier; no caps.** The senior seat and the `escalate`/`decision` edges were
  removed 2026-09-15; ask and attempt caps are gone too. The pair talk until green; the
  mentor owns boundary calls. Do not re-litigate.
- **Plan-time routing** (`v4-led` / `v4.1-led` chunks): deferred.
- **Rejected alternatives** (do not re-litigate): message content in the wake line;
  pre-spawning the mentor; rollback checkpoints; epochs/fencing tokens; long-lived
  mentor; model-held session ids; role-name routing for the pair.

## Verification

Run from `/home/vttin1/harness_research`, one tool at a time:

```
# persistent tests (includes property), 175
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q

# property only, 12
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/property -q

# opencode TS bridges: node:test resolver suite + autobind bind-before-first-pull probe
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools/test_ts_wiring.py -q

# acceptance (parse -> dry -> generate -> run), 59 across 4 features
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

## Working Tree

Uncommitted as of 2026-09-15:

- Modified (M5): `swarm-forge-tin/tools/{team,wiring}.py`, `swarm-forge-tin/harness.json`,
  `.opencode/tools/team.ts`, `.opencode/lib/team-autobind.ts`,
  `.opencode/agents/{orchestrator,mentor,coder,refactorer,architect}.md`,
  `harness_tests/persistent/tools/{test_team_behavior,test_tool_units}.py`,
  `harness_tests/persistent/tools/ts/wiring.test.ts`,
  `harness_docs/{README,ROADMAP,HARNESS_WIRING,PROJECT_STRUCTURE,TEAM_TOOL_DESIGN,WORKFLOW_ROUTING}.md`,
  `harness_docs/context_engineering/{mentor,state}.md`.
- Deleted (M5): `.opencode/agents/senior.md`.
- Modified (M2–M4): `swarm-forge-tin/tools/mailbox.py`,
  `.opencode/agents/*.md` (model routing), `opencode.json`,
  `harness_tests/persistent/{support.py,unit/test_wiring.py,tools/test_state_routing.py,acceptance/{runtime,steps,generator}.py}`,
  `harness_docs/TEST_PERSISTENCE_POLICY.md`.
- Added (untracked): `harness_tests/persistent/features/{task_state_layout,deterministic_coder_payload,deterministic_mentor_payload}.feature`,
  `harness_tests/persistent/property/test_team_properties.py`,
  `harness_tests/persistent/tools/{test_coder_payload,test_mentor_payload,test_team_behavior,test_mailbox_behavior,test_tool_units,test_mutation_runner,test_ts_wiring}.py`,
  `harness_tests/persistent/tools/ts/{ts-resolve.mjs,wiring.test.ts,autobind_probe.ts}`,
  `harness_tests/persistent/acceptance/{mutation_runner,run_mutation}.py`,
  `harness_docs/ROADMAP.md`, `harness_docs/context_engineering/`,
  `harness_docs/AGENT_INTERACTION_GRAPH.html`, `tmp/` (chunk seeds; disposable).
- Commit only when directed; a handoff never requires one.

## Resume Checklist

1. `git status` and `git diff --stat` — confirm the tree matches [Working Tree](#working-tree).
2. Restart opencode if the agent model config changed; then run the persistent suite and the
   acceptance pipeline; both must be green before new work (175 / 59).
3. Pick the next milestone from the table; move it to `In progress` here.
4. Follow TDD: failing behavior test first, then the smallest change, then the gates.
5. Append the milestone's evidence here and in `harness_docs/README.md` before handoff.
