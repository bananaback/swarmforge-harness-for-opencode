# Workflow

The people-process side of SwarmForge: who the roles are, how the orchestrator
dispatches them, how a phase chunk runs, and how work is verified and recovered.

Tool mechanics are in [TOOLS.md](TOOLS.md); `AGENTS.md` at the repo root is the
binding constitution and takes precedence over role prompts.

## Roles

| Role | Mode | Owns |
|---|---|---|
| `orchestrator` | primary | Dispatch and monitoring; the operator's control plane; no role work |
| `specifier` | subagent | Gherkin behavior specs and examples; mail-only, no chunk |
| `designer` | subagent | Class/method design, interfaces, SOLID boundaries, call sites; mail-only design seed |
| `task-breaker` | subagent | Topology: feature + design -> conflict-free chunks with disjoint allowlists and oracles |
| `coder` | subagent | TDD implementation of approved slices; unit + acceptance tests |
| `refactorer` | subagent | Behavior-preserving cleanup, coverage, CRAP/DRY, property tests |
| `architect` | subagent | Architecture, boundaries, code-quality/DRY verification; final gate |
| `mentor` | subagent | Advisory only; answers each `ask` with one `brief`; never edits or tests |

`specifier`, `coder`, `refactorer`, and `architect` are the four pipeline roles;
`orchestrator` and `mentor` support them. `designer` and `task-breaker` are the
out-of-band design pair (see [Design Pre-Phase](#design-pre-phase)).

## Model Routing

All eight agents run `opencode-go/deepseek-v4.1-flash`, variant `high`
(`thinking` enabled, `reasoningEffort: high`). Model variants are declared in
`opencode.json` (`mimo-v2.5`, `deepseek-v4-flash`, `deepseek-v4.1-flash`); the
agents use v4.1 explicitly. Changing a model or agent config requires an opencode
restart to take effect.

## The Pipeline

Two branches leave the orchestrator. The design branch is out-of-band and
optional; the execution branch is the durable mail chain. They converge at the
coder phase chunk: the specifier's handoff delivers the task, and the branch's
`team_open` seeds the chunk's brief/feature/design.

```
                               operator intent + task name

                                     ┌────────────┐
                                     │orchestrator│
                                     └────────────┘
                                            │
        A) design branch                    │                  B) execution branch
          (out-of-band)                     │                    (durable mail)
                ┌───────────────────────────┴───────────────────────────┐
                │                                                       │
             handoff                                                 handoff
                │                                                       │
           ┌────────┐                                              ┌─────────┐
           │designer│                                              │specifier│
           └────────┘                                              └─────────┘
                │                                                       │ .feature + IR
         design seed                                                    │
                │                                                       │
             handoff                                                    │
                │                                                       │
                │                                                       │
         ┌────────────┐                                                 │
         │task-breaker│                                                 │
         └────────────┘                                                 │
                │                                                       │
           plan.json                                                    │
                │                                                       │
                │                                                       │
                │                                                       │ writes chunk input:
       tools/taskbreak.py                                               │ brief / feature /
                │                                                       │ design / IR
                │                                                       │
           ┌─────────┐                                                  │
           │team_open│                                                  │
           └─────────┘                                                  │
                │                                                       │
                │                                                       │
                │                                                       │
                │                                                       │
                └───────────────────────────┬───────────────────────────┘
                                            │
                                            │
                                   ┌─────────────────┐
                                   │coder phase chunk│     worker + mentor
                                   └─────────────────┘
                                            │ mail handoff
                                            │
                                            │
                                            │
                                ┌──────────────────────┐
                                │refactorer phase chunk│   worker + mentor
                                └──────────────────────┘
                                            │ mail handoff
                                            │
                                            │
                                            │
                                 ┌─────────────────────┐
                                 │architect phase chunk│   final gate
                                 └─────────────────────┘
```

Each coder/refactorer/architect phase chunk runs as a `worker` + `mentor`
pair whose oracle is the chunk's test command; the design seed and plan are
staged to `features/design/<stem>.md` and
`artifacts/taskbreak/<stem>.plan.json`.

- Mail is the durable task chain. Each role sends its forward `handoff` and then
  `mail_done`; work is never carried in a chat turn.
- The orchestrator starts a feature by sending a `handoff` to `specifier` with
  the board-card task name and a one-line intent, then dispatching it.
- The **specifier** turns intent into a `.feature`, parses it with
  `gherkin-parser`, dry-checks it with `ir-dry-checker`, and hands off to the
  coder. It holds no chunk binding.
- Every **coder / refactorer / architect** dispatch also runs inside its own
  **phase chunk**: a fresh `worker` + `mentor` pair whose oracle is the chunk's
  test command.
- The **architect** is last. When it finishes, it may send follow-up handoffs
  (priority `00`) to coder/refactorer, or a functional-review handoff to the
  specifier, then reports; the specifier relays the result and asks for the next
  feature.

## Design Pre-Phase

The design pair is an out-of-band branch the orchestrator runs before the coder
chunk. It never replaces or delays the durable `specifier -> coder` handoff.

1. The orchestrator `mail_send`s a `handoff` to `designer` (feature task name plus
   a pointer to the feature) and dispatches it with `MAIL_WAITING`.
2. The **designer** reads the feature and source, writes one design seed to
   `<features root>/design/<stem>.md` with `TASK`, `DEFINITION OF DONE`,
   `INTERFACE CONTRACT`, `FILES`, `VOLATILITY`, and `SELF-AUDIT` sections, then
   hands off to `task-breaker`.
3. The **task-breaker** reads the feature and design seed, writes one plan to
   `<artifacts root>/taskbreak/<stem>.plan.json`, and completes. It sends no mail
   down the four-role chain; the orchestrator consumes the plan directly.
4. The orchestrator turns the plan into chunk seeds with
   `python3 <pack>/tools/taskbreak.py --root <workspace> --plan <plan>` and then
   dispatches the coder chunk normally.

Neither role holds a team seat or runs an oracle; both are mail-only. The full
plan contract and the branch procedure are in
[TOOLS.md § Task-Breaker Bridge](TOOLS.md#task-breaker-bridge-taskbreakpy) and the
role prompts.

## Dispatch Loop (orchestrator)

1. Run `mail_status`.
2. Dispatch every role that has queued mail and **no** in-process holder.
3. Dispatch with the `task` tool: `subagent_type` is the role, `description`
   names the role, and `prompt` is exactly the wake line — `MAIL_WAITING: run
   mail_pull` for mail, `TEAM_WAITING: run team_pull` for a bound team seat.
4. Store the returned `task_id` and reuse it to resume that session.
5. Dispatch at most one role session at a time; the shared directory and tools
   serialize.
6. Never dispatch a role that already holds an in-process item. On a double
   dispatch, only the owning session continues.
7. After a session returns, run `mail_status` again and dispatch the next role.
8. Stop when nothing is queued or in process; report the drained state.

The wake line never carries the task — the mailbox and chunk state are the source
of truth.

## Phase Chunks (worker + mentor)

There is no senior tier and no ask or attempt cap: the worker and mentor talk
until the oracle is green, and the mentor owns boundary calls directly.

### Orchestrator: open then dispatch

For each coder/refactorer/architect dispatch:

1. `team_open <task> --role <role> [--brief F] [--feature F] [--design F]` —
   seed the chunk from the inbound mail handoff: full brief, the feature, and the
   design chunk (interface contract, allowlist/call sites). There is no pack
   size bound.
2. Dispatch the role with the wake line `TEAM_WAITING: run team_pull`.
3. The `team-autobind` plugin binds the fresh session to its `SPAWN_PENDING`
   seat before the child's first tool call (`team_bind` is the manual fallback).
4. After each dispatch, run `team_status --ready`: `SPAWN_PENDING` means spawn
   that seat; `queued` means wake the bound session.
5. When the worker completes and forwards its mail handoff, `team_close` the
   chunk (the workers and mentor are abandoned together).

Chunk ids in use: the feature name for the coder phase, `<feature>/refactorer`
and `<feature>/architect` for the later phases. Nested ids are visible to
`team status --ready` (recursive), so the autobind plugin binds the
later phase chunks without the manual `team_bind` fallback.

### The worker's turn

```
team_pull                     -> chunk item; binds on first pull
team_context                  -> deterministic payload (11 sections for a coder)
team_journal readback         -> goal, constraints, done, understanding
team_journal plan             -> options, choice, rationale, expect
edit → team_attempt           -> records ATTEMPT: N, returns the oracle output
     → team_journal result --attempt N
... repeat while progress is real ...
team_send --to mentor --kind ask   # when the next change would be a guess
team_done                     # stop; the mentor brief arrives on the next pull
... resume ...
mail_send handoff (next role) -> always, even when nothing changed
mail_done                     -> only if inbound mail was pulled
team_done
```

The worker journals **unconditionally** (whether or not it asks the mentor) and
never edits the chunk's tests or the oracle command to make a run pass. The
oracle is the only source of green.

### The mentor's turn

```
team_pull                     -> the ask
team_context                  -> mentor payload (system prompt + GOAL/RULES/TRAIL/ASK/FAILURE)
team_send --to worker --kind brief
team_done
```

One brief per ask: a decision, the reason, and the next change to try. Later asks
on the same chunk return as the mentor's next pull. Dialogue lives in session
turns; the mentor never journals, edits, or runs the oracle.

### Who calls what

```
worker : team_pull · team_context · team_journal · team_attempt · team_send(ask) · team_done
mentor : team_pull · team_context · team_send(brief) · team_done
orch   : team_open · team_bind · team_status · team_close · mail_send(start) · mail_status

plus, per role: mail_pull / mail_send / mail_done for the durable task chain.
Models never pass a task id, their own seat, or a session id — the tool resolves
them from the session binding; the only thing a model names is the target seat.
```

## Handoffs

- Forward the chain **always**, even when nothing changed: coder → refactorer,
  refactorer → architect.
- Preserve the task name received; do not invent one.
- `mail_done` only if inbound mail was pulled; skip it when `mail_pull` printed
  `NO_TASK`.
- `team_done` completes the chunk item.
- Keep the handoff `message` (≤ 300 chars) to the files touched and the one fact
  the next role needs, e.g. `touched: src/cart.py, tests/unit/test_cart.py;
  pytest green`.
- **Verification handoffs** from the architect are handled in the dispatch that
  delivers them: run unit and acceptance tests, fix failures, then `mail_done`
  and `team_done`. Do not forward them.
- The architect sends follow-up handoffs only when there is follow-up work, and
  sends completion notes nowhere.

## Failure, Recovery, Stuck Sessions

**Tool-failure protocol (temporary, all roles).** If a `mail_*` or `team_*` call
fails, stop immediately, do not work around it, and report the exact error as the
final chat message. The orchestrator diagnoses, hot-fixes the tooling or prompt,
verifies with the tool's CLI or the harness tests, and resumes the session.

**Unbound session.** `session is not bound to any team seat` means the
orchestrator did not bind this dispatch to its phase chunk. Stop and report; never
rationalize it away and continue.

**Stuck session.** The operator stops it with ESC and confirms it is stopped.
Only then may the orchestrator dispatch a replacement, passing `takeover: true`
on the next pull. Never take over from a live session. Resume the stored
`task_id` when possible — the owning session needs no takeover to continue its
own item.

**Failed chunk.** There is no rollback machinery by design; a red chunk is
reported to the operator and the pair is abandoned.

## Switching Projects

- Point at another project with `SWARM_CONFIG=/path/to/project/harness.json`, or
  edit `workspace_root` in `swarm-forge-tin/harness.json`. Configs live in the
  pack; a wired project keeps its source tree source-only.
- Before switching, clean the shared areas:
  `swarm-forge-tin/tools/harness clean all` (or `hot`, `state`, `artifacts`
  individually). `clean hot` is required, not optional: the shared `hot_tests/`
  otherwise holds two projects' generated entry points, which collide in one
  pytest session.
- `clean state` refuses while mail/team items are in process unless `--force`.
- Never delete a persistent test root.

## Anti-Goals

- The orchestrator does not write specs, code, or tests, and does not run
  acceptance, tests, or quality tools.
- Roles do not create worktrees, switch branches, or commit unless explicitly
  directed; a handoff never waits for or references a commit.
- Roles do not inspect, diff, merge, or rebase another role's uncommitted work.
