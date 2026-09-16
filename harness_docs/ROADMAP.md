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
| M6 | Sample-project validation | **In progress** | committed sample projects green through the full pipeline |
| M7 | Prompt engineering for all six agents | **Done** | every agent prompt revised; suite and acceptance green |
| M8 | Add OOP/SOLID designer and task-breaker agents | **Done** | two prompts; task-breaker output feeds `team_open`; gates green |
| M9 | Validate the design + execution branches together | **Done** | one feature runs both branches with no manual glue |
| M10 | Tool + durable-state correctness audit | **Done** | contracts, recovery, and concurrency proven; known limitations resolved |
| M11 | Live web dashboard for agent/task progress | Backlog | read-only live view of mail, tasks/chunks, and journals |
| M12 | Gherkin features as the single source of truth | **Done** | every delivered requirement has an executable feature; downstream TDD proves it |
| M13 | Structured failure log + self-repair review | Backlog | every agent/tool failure captured, grouped, and replayable for later fixes |

## Current State

Self-hosting and green. The pack points at this repository; all eight agents run
`opencode-go/deepseek-v4.1-flash` variant `high`.

**This is a working baseline, not a production-ready harness.** Two
reliability questions are still open and gate adoption:

1. **Tool and state correctness** — each tool and the durable state are tested on
   happy paths and their documented contracts, not under stress, concurrency, or
   crash recovery.
2. **Wiring portability** — the pack is proven only self-hosting; no committed
   sample project exercises it end to end.

M9 (branch compatibility) is done at the tool level: a deterministic integration
run drives both branches through the real CLIs on a scratch project with no
manual glue, and its one real seam defect (nested phase chunks invisible to
`status --ready`) is fixed. See
[M9-VALIDATION.md](M9-VALIDATION.md). M12 (specification coverage) is done: every
documented tool command, refusal, state invariant, context payload, recovery
path, and pipeline seam has an executable Gherkin scenario, wired to downstream
TDD and proven by mutation. M10 (tool/state correctness) is now done: the
contract, recovery, and concurrency slices are executable and green, so the
remaining gate is M6 (portability); do not treat the harness as production-ready
until it passes. M6 is in progress: the `todo` sample is wired through a
pack-side config (`swarm-forge-tin/harness.todo.json`) and validated at the tool
level — its project tests, acceptance, ruff/CRAP/DRY, and a mail/team pipeline
smoke are green with nothing written into the sample tree; the integration
fixture and the live eight-agent run remain. M11 (dashboard) and M13 (structured
failure log for later self-repair) are follow-on goals.

- Wiring: `harness.json` + `tools/wiring.py` + `.opencode/lib/wiring.ts` +
  `tools/harness` (`config` / `status` / `clean`).
- State: `tasks/<UTC-date>/<task>/<NN-role>/{input,journal.jsonl,output}` with a
  `done/` mirror; write-once inputs, append-only journals.
- Tools: `mailbox.py` (durable mail), `team.py` (seat routing, journal, oracle
  attempts, deterministic context payloads), and `taskbreak.py` (task-breaker
  plan → `team_open` seeds).
- Acceptance: 22 features, 156 scenarios, 229 executions green.
- Quality: 373 persistent tests (47 property); ruff clean; CRAP 0 functions above
  10 (scoped); DRY 0 clones. Mutation (the 14 mutation-run features — every M12
  feature plus the original coder payload): 377 mutants / 277 killed / 100
  survived / 0 errors, every survivor documented as equivalent.
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

The reliability program: make the baseline trustworthy before production use.
M9 validated the branch seams, M12 made the features the single source of
truth, and M10 proved the tool/state contracts; the remaining gate is M6
(portability). M11 and M13 are follow-on products rather than gates.

- **M9 — Validate the design and execution branches together (done).** Both
  branches ran on one scratch feature with no manual glue:
  `specifier → designer → task-breaker → coder → refactorer → architect`,
  51 tool calls, every seam asserted, ending drained. The one real defect it
  surfaced — nested phase chunks (`cart/refactorer`) invisible to
  `team status --ready`, which forced the manual `team_bind` fallback — is
  fixed. Evidence and friction list: [M9-VALIDATION.md](M9-VALIDATION.md);
  run log: `dump/m9/runlog.json`. Persistent suite and acceptance green.

- **M10 — Tool and durable-state correctness audit (done, gate passed).** Goal: prove each
  tool's contract and the state machine beyond the happy path, not just cover
  them. Progress: the `M10-known-limitations` slice is resolved — the dead
  `sealed` field and guards are gone, `bind`/`close` resolve a task across the
  live date folders, `harness clean state` counts live team tasks, and the TS
  `findConfig` walks up and falls back like the Python resolver; the one
  remaining limitation (the cosmetic `--ready` phantom opening-role seat) is
  accepted with a one-line rationale. The `M10-tool-state-audit` contract slice
  is also executable and green — mail `done` ownership/`--id`/`status` holder,
  team `open` role/task-name and `bind` seat validation plus the worker-kind
  restriction, and the bare `clean` default target — each mapped to a scenario
  in [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md); no tool behavior changed for
  the audit. The `M10-stress-recovery` slice is now executable and green: mail
  recovery (`done` without an in-process item is refused and leaves the queue; a
  completed item is never re-claimed; a re-send after completion reports
  `QUEUED`; a corrupt queued or in-process item is refused naming `corrupt`, exit
  2, nothing moved) and team recovery (session-resolved `context`/`done` find a
  task filed under an earlier UTC date; a repeated `done` appends and reports
  `NO_TASK`; a corrupt `task.json` fails a `bind` naming `corrupt`), each mapped
  to a scenario in [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md) as
  `mail_recovery`/`team_recovery`. `mailbox.read_item` and `team.load_task_json`
  are the single fail-closed readers for mail items and task records. The
  `M10-concurrency` slice closes the milestone: real operating-system processes
  prove the locks — two sessions pulling one role at the same time leave exactly
  one owner and refuse the loser naming the winner, two identical handoffs sent
  concurrently queue exactly one item (`DUPLICATE` for the other), and two
  concurrent journal appends keep distinct sequence numbers. The per-role and
  per-task guards are the real `durable_store.lock` `flock`, so no tool behavior
  changed: the slice added step handlers and focused unit tests only (see
  `duplicate_dispatch`/`lock_contention` in
  [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md)). Scope:
  - contract audit of `mailbox`, `team`, `taskbreak`, `harness`, and `wiring`:
    every command's invariants, refusals, exit codes, and ownership rules;
  - state invariants: write-once inputs, append-only journals, single-owner
    claims, atomic writes, lock coverage, `clean`/`--force` safety;
  - stress and recovery: property/fuzz tests plus duplicate dispatch,
    interrupted `mail_pull`/`team_done`, lock contention, corrupt JSON, and the
    midnight date boundary;
  - resolve or explicitly accept every entry in
    [ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations).
  Exit criteria met: each limitation fixed or accepted with a one-line
  rationale; property, crash-recovery, and concurrency contracts green; no
  data-loss path found; CRAP/DRY clean.

- **M6 — Validate against committed sample projects (in progress).** Goal: prove
  the pack runs against a project other than itself, using committed sample
  projects rather than an arbitrary external one, so the check is deterministic
  and repeatable. One sample is wired and validated at the tool level:
  - `samples/todo/` holds source only (`src/todo.py`); the config lives in the
    pack (`swarm-forge-tin/harness.todo.json`) and points `workspace_root` at the
    sample and the shared roots back into the pack. Configs live only under
    `swarm-forge-tin/`; a sample is just a project tree the config points at.
  - Its authored tests, features, and acceptance live in the dedicated pack-side
    root `swarm-forge-tin/project_tests/persistent/`; generated entry points go to
    the shared `hot_tests/`, reports and coverage to `dump/`, and mail/team state
    to `.swarmforge/`. Nothing is written into the sample tree.
  - Green against the sample: `harness status`/`config` resolve the sample paths
    and `kind: project` root; 8 project tests; 4 acceptance executions
    (parse -> dry -> generate -> run); ruff clean; DRY 0 clones; CRAP 0 functions
    above 10; a `mail`/`team` smoke drives the specifier -> coder handoff, chunk
    open/bind/pull/context, and drains. Pack self-host suite still 373.
  - Findings: the shared `hot_tests/` collides generated entry points from two
    projects in one pytest session (module-name clash on `runtime`/`steps`), so
    `harness clean hot` is required on project switch — the documented switch
    step; and bytecode leaked into the sample tree from the acceptance runner and
    chunk oracles, now guarded by `sys.dont_write_bytecode` in the generated
    entrypoint, `PYTHONDONTWRITEBYTECODE` in the acceptance runner, and
    `PYTHONDONTWRITEBYTECODE` in `team.py run_oracle`.
  Remaining: an integration fixture test that drives the sample inside the suite,
  a live eight-agent run with `SWARM_CONFIG`, and committing the fixture. Scope:
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

- **M11 — Live web dashboard for agent/task progress (backlog, later).** Goal:
  watch a run in the browser as it happens — which roles are dispatched, what is
  queued or in process, where each feature is in the pipeline, and the chunk
  journals and oracle attempts as they accrue. Scope:
  - read-only: the dashboard renders the durable state (`<state_root>/mail` and
    `<state_root>/tasks`) and never writes it; the tools stay the only writers;
  - reuse the tools' read models and `<pack>/tools/wiring.py` for paths — do
    not re-walk or reimplement queue/task discovery in the dashboard;
  - live updates (poll or push) for mail queues per role, `task.json` seat
    state, `team status --ready`, and appended `journal.jsonl`/`output/` lines;
  - a task/board list plus a per-task drilldown (chunks, seats, journal
    timeline, attempt output, pipeline position);
  - separate the testable data-shaping/serialization layer from the
    environmentally unsuitable server/browser boundary so the shapers carry the
    tests.
  Exit criteria: a live run is visible end to end in the browser; the data
  layer reuses the tools' read models; no state writes; unit tests for the
  shapers; ruff/CRAP/DRY clean.

- **M12 — Gherkin features as the single source of truth (done, gate passed).** Goal: the
  feature files are the one artifact that says how the harness is supposed to
  behave, and the suite proves that behavior rather than trusting that it works.
  Today four features cover a fraction of the delivered tools and contracts, so
  a regression can ship with green tests. Scope:
  - audit every delivered requirement against the features root and list the
    gaps (each public tool command, refusal, state invariant, context payload,
    recovery path, and pipeline seam);
  - write deterministic `.feature` files for the gaps; keep the
    `gherkin-parser` -> `ir-dry-checker` -> generator -> runtime pipeline and
    regex step handlers as the only spec path;
  - wire each new feature to downstream TDD: step handlers delegate to the
    testable modules, focused unit/property tests cover the same behavior, and
    the generated acceptance entry points exercise every example;
  - use `gherkin-mutator` on the new features so example values are proven to
    reach the implementation, not just replayed;
  - keep a coverage map from requirement/command to feature so a new behavior
    without a scenario is visible.
  Exit criteria: every documented command and contract has at least one
  scenario; no requirement without a feature; new features pass parse, dry
  check, generation, and execution; mutation kills on the new features; suite
  and acceptance green.
  Evidence: 16 features / 130 scenarios / 203 executions green; 319 persistent
  tests; 377 mutants / 277 killed / 100 documented-equivalent survivors / 0
  errors across the 14 mutation-run features (every M12 feature); ruff clean,
  CRAP 0 functions above 10, DRY 0 clones. Requirement traceability:
  [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md); mutation rationale:
  `harness_tests/persistent/acceptance/MUTATION-RATIONALE.md`.

- **M13 — Structured failure log + self-repair review (backlog, later).** Goal:
  when an agent cannot do something — a tool call fails, a refusal or unexpected
  state appears — the harness records it in one organized, durable log so a
  later pass (or the harness itself) can read the failures and fix the cause
  instead of guessing. Scope:
  - define a failure-record schema: timestamp, role, session, task/chunk, tool,
    command/args, exit/refusal, expected vs actual, error text, the durable
    state ids involved, and whether a retry happened;
  - capture on the documented failure paths (`mail_*`/`team_*` exit-2
    refusals and validation errors, tool exceptions, the role tool-failure
    stop reports, autobind skips, oracle infrastructure errors) without
    becoming a second source of truth;
  - store append-only under the configured state/artifacts root, grouped and
    deduplicated by signature with counts and first/last seen;
  - provide a read/replay surface — a CLI (and the M11 dashboard feed) — so a
    recorded failure can be inspected and its command replayed to verify a fix;
  - keep the capture layer testable and the write path atomic and locked.
  Exit criteria: schema documented; every documented failure path is captured
  and covered by a test; a recorded failure replays; no writes outside the
  configured roots; suite and acceptance green.

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

M10 resolved or explicitly accepted these; tracked in
[ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations):

- Resolved (`M10-known-limitations`): `sealed` removed from `task.json` and all
  guards.
- Resolved (`M10-known-limitations`): `bind`/`close` resolve a task by name
  across the live date folders.
- Resolved (`M10-known-limitations`): `harness clean state` counts live team
  tasks under `tasks/**` as well as mail in-process items.
- Resolved (`M10-known-limitations`): the TS `findConfig` walks up from the CWD
  and falls back to the pack, matching `wiring.py`.
- Accepted: `--ready` lists a phantom opening-role seat (cosmetic; the autobind
  plugin filters to `worker`/`mentor`).

## Verification

Run from the repository root, one tool at a time:

```bash
# persistent tests (373; property 47)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q

# M9 branch integration (both branches, one feature)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  persistent/tools/test_branch_integration.py -q

# property only (47)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/property -q

# TS bridges: node:test suite + autobind bind-before-first-pull probe
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest persistent/tools/test_ts_wiring.py -q

# acceptance (parse -> dry -> generate -> run; 22 features, 229 executions)
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

# M6 sample project (samples/todo) via the pack-side config
swarm-forge-tin/tools/harness --config swarm-forge-tin/harness.todo.json status
cd swarm-forge-tin/project_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
python3 swarm-forge-tin/project_tests/persistent/acceptance/run_acceptance.py \
  --config swarm-forge-tin/harness.todo.json
```

## Resume Checklist

1. `git status` and `git diff --stat` — confirm a clean or understood tree.
2. Restart opencode if an agent/model config changed; then run the persistent
   suite and the acceptance pipeline. Both must be green before new work (373 /
   229).
3. Pick the next milestone; move it to `In progress` here.
4. Follow TDD: failing behavior test first, smallest change, then the gates.
5. Record the milestone's evidence here and in [README.md](README.md) before
   handoff.
