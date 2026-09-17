# Dispatch

The `prompt` the orchestrator hands to the `task` tool when it calls a role. Only
the orchestrator dispatches; a role never calls `task` and never forwards.

```
TASK: <stable task name; the same name the whole way down>
ROLE: <specifier | coder | refactorer | architect>
FEATURE: <feature path, or none>
BRIEF:
<the chunk brief: what this role must achieve>
DEFINITION OF DONE:
- [ ] <observable check>
ALLOWLIST:
<one path per line; the role edits nothing outside it>
ORACLE: <the exact command; its exit code is the proof>
CONTRACT: <shared interface, only when the chunk crosses a boundary; otherwise omit>
INBOUND:
<the previous role's final message, verbatim>
```

## Who supplies what

The orchestrator assembles every field. It does no role work: it copies scope from
the operator's brief and the previous role's message, and the standard commands
from the constitution.

- `ALLOWLIST`: the paths named by the previous message's `FILES`, plus the source
  and test areas the operator named. A fresh feature starts from its feature
  artifact and the roots it touches.
- `ORACLE`: the role's standard verification. Coder: the persistent suite (or the
  chunk's pinned test). Refactorer: CRAP, then DRY, then the suite. Architect: DRY,
  then ruff, then the suite. Copy the exact command from `<pack>/constitution.md`.
- `CONTRACT`: include it only when the chunk shares an interface with another chunk.
  Sequential single-tree work has one chunk at a time, so omit it by default.

Do not ask the role to dispatch the next role. It answers with its template and a
`NEXT` line; the orchestrator reads `NEXT` and makes the next call.
