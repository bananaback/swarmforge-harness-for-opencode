# Communication

The orchestrator is the only dispatcher: it calls one role at a time with the `task` tool and reads that role's final message. Roles run as subagents (`subagent_depth` is 1) and never call `task`.

## Calling
- `subagent_type` is the role; `prompt` is the message from `<pack>/protocol/dispatch.md`. Omit `task_id` to start fresh; pass the returned `task_id` to resume that session. The result is the callee's final message.

## Answering
- End the turn with the message from `<pack>/protocol/<role>.md`. Never call `task`. A role's `NEXT` names the role the orchestrator dispatches next.
- The architect's terminal message is relayed to the pack; recipients verify and stop, they do not forward it.

## Dispatch Rule
One decision per returned message:
- `STATUS: done` + oracle evidence (specifier: also `APPROVED: yes`) -> dispatch `NEXT`.
- `STATUS: blocked`/`needs-input` -> stop; surface `ASK` with `question`. A blocked message never advances.
- specifier `APPROVED: no` -> do not dispatch the coder.
- missing or contradictory fields -> re-dispatch that role once; still malformed -> escalate.
- `NEXT` absent or unknown -> escalate; never guess.
- Architect defect: `NEXT` names the role to fix and `FIX` carries the change; dispatch it, then re-run the architect. The architect never certifies its own fix; a second block on the same defect -> escalate.

## Field Ownership
- The orchestrator fills chunk fields by copying: `ALLOWLIST` = previous `FILES` + operator-named areas; `ORACLE` = the role's standard command in `engineering.md`; `CONTRACT` only when a chunk crosses a boundary (omit in sequential single-tree).
- Chunks may run concurrently only with disjoint allowlists; a chunk never edits outside its allowlist. Never ask a role to dispatch another role.

## Evidence
- Carry the oracle command and its exit code; green without an oracle result is not evidence. No role certifies its own work.

## Gates
- The specifier gates on operator approval (`question`: Approve / Request changes / Stop) and reports `APPROVED: yes` only after Approve.
- Ambiguity, contradiction, or a spec/test conflict: ask with `question`; never guess or carry it in chat.
- Passing architect gate (`STATUS: done`, `NEXT: operator`): relay it; every non-specifier role re-runs unit and acceptance tests, fixes failures, then stops.
- A defect is `STATUS: blocked`, `NEXT` the fixing role, `FIX` the change.

# Project
- Four roles plus an orchestrator: specifier, coder, refactorer, architect. Language: Python.
- Do not change another role's prompt or ownership without explicit direction.
