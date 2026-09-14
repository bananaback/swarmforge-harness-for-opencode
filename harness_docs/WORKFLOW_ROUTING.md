# Workflow Routing Intent

**Captured:** 2026-09-11
**Companions:** `TEAM_TOOL_DESIGN.md` (routing mechanics), `TEAM_JOURNAL_EXAMPLE.md` (journal depth)
**Implemented in:** `opencode.json`, `.opencode/agents/*.md` (restart required to load)

## 1. Model tiers

| tier | model id | price in/out | role character |
|---|---|---:|---|
| mimo | `opencode-go/mimo-v2.5` | $0.14 / $0.28 | dump, cheap loop |
| v4 | `opencode-go/deepseek-v4-flash` | $0.15 / $0.60 | premium, smart |
| v4.1 | `opencode-go/deepseek-v4.1-flash` | $0.15 / $0.60 | smartest, expensive |

Both DeepSeek tiers expose reasoning effort `low` / `high` / `max`; `low` and `high` are disabled and `max` is the only variant. MiMo V2.5 exposes no effort options.

## 2. Role → model routing

| role | model | variant | advisors |
|---|---|---|---|
| orchestrator | v4 | max | none |
| specifier | v4 | max | none |
| coder | mimo | — | triple |
| refactorer | mimo | — | triple |
| architect | mimo | — | triple |
| mentor | v4 | max | triple (middle) |
| senior | v4.1 | max | triple (top) |

Intent:
- The orchestrator stays on v4: its loop is small, but dispatch and binding errors cascade.
- The specifier stays on v4: spec semantics have no oracle, so errors propagate downstream.
- coder, refactorer, and architect run the cheap loop on mimo; each is oracle-gated (unit/acceptance tests, CRAP/DRY).
- The triple applies only to roles that operate by mimo.

## 3. Triple routing

```
worker (mimo) --ask--> mentor (v4) --brief--> worker
                          |
                       escalate
                          v
                   senior (v4.1) --decision--> mentor --brief--> worker
```

- Seats: `worker` = coder / refactorer / architect; `mentor` = v4; `senior` = v4.1.
- Edges are fixed and tool-enforced: worker→mentor `ask`, mentor→worker `brief`, mentor→senior `escalate`, senior→mentor `decision`. Models name only the target seat; chunk and session ids never enter model context.
- The worker asks once per chunk, only for a brief/oracle contradiction, input outside the allowlist, or a concrete decision with options. Never "is my code correct?" — the oracle answers that.
- After a brief the worker gets two oracle runs; stop early when the same failure signature repeats twice.
- Loop caps: 3 worker attempts, 1 ask, 2 post-brief runs, 1 senior ruling.
- The oracle is the only green. Tests and the oracle command are never edited to pass.
- Cheap sampling pays only with an external verifier; escalation triggers on information stagnation, not attempt count.

## 4. Work routing

- Single flow: pipeline mail is the durable task chain (`specifier → coder → refactorer → architect`); each role sends its forward `handoff` and then `mail_done`.
- Every coder/refactorer/architect phase also runs inside its own phase chunk (a fresh triple): the orchestrator opens the chunk seeded from the mail handoff, binds the role's session as `worker`, and wakes it; the role pulls both its chunk item and its mail task, journals unconditionally (readback/plan/result), and asks the mentor only when it needs a decision.
- The specifier (v4) is mail-only and holds no chunk binding.
- The `team-autobind` plugin (`.opencode/plugins/team-autobind.ts`) binds each spawned session automatically: on a `TEAM_WAITING` wake the `chat.message` hook matches the agent to the single `SPAWN_PENDING` seat (coder/refactorer/architect → worker, mentor → mentor, senior → senior) and binds before the child's first tool call. `team_bind` remains the manual fallback when the hook skips.
- Wake lines carry nothing:
  - `MAIL_WAITING: run mail_pull` for mail (specifier dispatches).
  - `TEAM_WAITING: run team_pull` for a bound team seat (coder/refactorer/architect phase dispatches).
- The orchestrator alone calls `team_open`, `team_bind`, `team_status`, `team_close`; it never pulls, sends, journals, or completes seat work.
- The specifier and orchestrator have all team seat tools denied.
- Sessions are never reused across chunks; `team_close` abandons a phase chunk's sessions together.
- An unbound `team_*` call (`session is not bound to any team seat`) is an orchestrator binding failure: the role stops, reports the exact error, and never rationalizes it away and continues.

## 5. Open items

- The mentor-takeover run (one run) is not wired; the mentor is advisory-only (no edit, no bash).
- Spawn → bind → wake: resolved by the `team-autobind` plugin — the `chat.message` hook binds the fresh session to its `SPAWN_PENDING` seat on the wake message, so the standby dispatch is gone. Remaining risk: hook timing vs the child's first tool call (probed once live after a restart; fallback is the orchestrator's manual `team_bind`).
