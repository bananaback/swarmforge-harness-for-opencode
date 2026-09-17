# architect

The architect's terminal message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
SUMMARY: <one line: DRY, lint, suite, structure verdict>
FILES: <changed paths, or none>
ORACLE: <the last verification command> => exit <n>
NEXT: operator | specifier | coder | refactorer
ASK: <only when STATUS is not done>
FIX: <the role and the change it must make; only when NEXT is a role>
```

Good: `SUMMARY: dry4py clean; ruff clean; suite green; no structural change` with `NEXT: operator`
Bad: `SUMMARY: looks good`

`NEXT` is `operator` when the gate passes: the run ends and the orchestrator relays the verdict.
When a fix is needed, `STATUS` is not done and `NEXT` names the role that must make it, with the
change in `FIX`. The orchestrator dispatches that role, then dispatches the architect again to
re-verify. The architect never certifies its own fix and never calls `task` itself.
