# Protocol

How the pipeline talks. The orchestrator is the only caller: it invokes one role
at a time with the opencode `task` tool and reads that role's final message as
the result. A role runs as a subagent (`subagent_depth` is 1) and never calls
`task` itself; it answers with its template, and the orchestrator dispatches the
role named by `NEXT`.

## Calling a role

`task` with:

- `subagent_type`: the role (`specifier`, `coder`, `refactorer`, `architect`).
- `prompt`: the message from `dispatch.md`.
- `task_id`: omit it to start a fresh session; pass the id returned by an earlier
  call to resume that session. Resuming is the cache hit: the session keeps its
  context instead of rebuilding it.

The result is the callee's final message. Only the orchestrator passes `task_id`.

## Answering

End your turn with the message from your role template:

| Role | Template |
|---|---|
| specifier | `specifier.md` |
| coder | `coder.md` |
| refactorer | `refactorer.md` |
| architect | `architect.md` |

Never call `task` from a role. `NEXT` names the role the orchestrator dispatches
next, not a role the role itself calls.

## Editing

These files are plain text. Change a field name, add a line, or delete one here and
every role picks it up on its next turn. Keep the field names stable: another role
reads them, and a missing field is a silent bug.
