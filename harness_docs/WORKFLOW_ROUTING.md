# Workflow Routing Intent

**Captured:** 2026-09-11 · **Updated:** 2026-09-14 (reasoning roles moved to v4.1 `high`)
**Companions:** `TEAM_TOOL_DESIGN.md` (routing mechanics), `TEAM_JOURNAL_EXAMPLE.md` (journal depth)
**Implemented in:** `opencode.json`, `.opencode/agents/*.md` (restart required to load)

## 1. Model tiers

| tier | model id | price in/out | role character |
|---|---|---:|---|
| mimo | `opencode-go/mimo-v2.5` | $0.14 / $0.28 | dump, cheap loop |
| v4 | `opencode-go/deepseek-v4-flash` | $0.15 / $0.60 | premium, smart |
| v4.1 | `opencode-go/deepseek-v4.1-flash` | $0.15 / $0.60 | smartest, expensive |

Reasoning-effort availability: `v4.1` exposes `high` and `max` (`low` disabled); `v4`
exposes `max` only (`low` and `high` disabled); MiMo V2.5 exposes no effort options.
Current implementation: all six roles run `v4.1` at `high`; the mimo and v4 tiers below
are the original intent and are currently unused.

## 2. Role → model routing

| role | model | variant | advisors |
|---|---|---|---|
| orchestrator | v4.1 | high | none |
| specifier | v4.1 | high | none |
| coder | v4.1 | high | mentor |
| refactorer | v4.1 | high | mentor |
| architect | v4.1 | high | mentor |
| mentor | v4.1 | high | — |

Intent:
- The orchestrator runs v4.1: its loop is small, but dispatch and binding errors cascade.
- The specifier runs v4.1: spec semantics have no oracle, so errors propagate downstream.
- coder, refactorer, and architect are oracle-gated (unit/acceptance tests, CRAP/DRY).
- The pair applies only to the worker and mentor seats; there is no senior tier.


## 3. Pair routing

```
worker (v4.1) --ask--> mentor (v4.1) --brief--> worker
```

- Seats: `worker` = coder / refactorer / architect; `mentor` = advisor. There is no senior tier.
- Edges are fixed and tool-enforced: worker→mentor `ask`, mentor→worker `brief`. Models name only the target seat; chunk and session ids never enter model context.
- The worker asks the mentor whenever the next change would be a guess: a brief/oracle contradiction, input outside the allowlist, or a concrete decision with options. Never "is my code correct?" — the oracle answers that.
- There is no ask cap and no attempt cap; the pair exchange as many asks and briefs as the problem needs, and the oracle loop keeps running while progress is real.
- The oracle is the only green. Tests and the oracle command are never edited to pass.
- The mentor owns boundary calls directly (changing the frozen contract, editing outside the allowlist, a new dependency); there is no escalation tier.

## 4. Work routing

- Single flow: pipeline mail is the durable task chain (`specifier → coder → refactorer → architect`); each role sends its forward `handoff` and then `mail_done`.
- Every coder/refactorer/architect phase also runs inside its own phase chunk (a fresh pair): the orchestrator opens the chunk seeded from the mail handoff, binds the role's session as `worker`, and wakes it; the role pulls both its chunk item and its mail task, journals unconditionally (readback/plan/result), and asks the mentor whenever it is stuck, with no cap.
- The specifier (v4.1) is mail-only and holds no chunk binding.
- The `team-autobind` plugin (`.opencode/plugins/team-autobind.ts`) binds each spawned session automatically: on a `TEAM_WAITING` wake the `chat.message` hook matches the agent to the single `SPAWN_PENDING` seat (coder/refactorer/architect → worker, mentor → mentor) and binds before the child's first tool call. `team_bind` remains the manual fallback when the hook skips.
- Wake lines carry nothing:
  - `MAIL_WAITING: run mail_pull` for mail (specifier dispatches).
  - `TEAM_WAITING: run team_pull` for a bound team seat (coder/refactorer/architect phase dispatches).
- The orchestrator alone calls `team_open`, `team_bind`, `team_status`, `team_close`; it never pulls, sends, journals, or completes seat work.
- The specifier and orchestrator have all team seat tools denied.
- Sessions are never reused across chunks; `team_close` abandons a phase chunk's sessions together.
- An unbound `team_*` call (`session is not bound to any team seat`) is an orchestrator binding failure: the role stops, reports the exact error, and never rationalizes it away and continues.

## 5. Open items

- Decided: the mentor is advisory-only (no edit, no bash) and there is no mentor-takeover run. The pair's free ask/brief dialogue replaces both the senior tier and the takeover concept; the budget locus is "none" — no ask or attempt caps.
- Spawn → bind → wake: resolved by the `team-autobind` plugin — the `chat.message` hook binds the fresh session to its `SPAWN_PENDING` seat on the wake message, so the standby dispatch is gone. The bind-before-first-pull timing is now asserted automatically: `harness_tests/persistent/tools/ts/autobind_probe.ts` runs the real `autoBindPendingSeat` and `test_ts_wiring.py` checks `status --ready` flips to `queued` and the first `pull` returns `RESUMED`. Remaining risk: live hook ordering inside opencode itself (the fallback stays the orchestrator's manual `team_bind`).
