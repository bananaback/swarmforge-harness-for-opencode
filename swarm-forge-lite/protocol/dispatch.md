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
INBOUND:
<the previous role's final message, verbatim>
```

Do not ask the role to dispatch the next role. It answers with its template and a
`NEXT` line; the orchestrator reads `NEXT` and makes the next call.
