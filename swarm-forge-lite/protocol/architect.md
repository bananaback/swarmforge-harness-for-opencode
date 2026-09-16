# architect

The architect's terminal message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
SUMMARY: <one line: DRY, lint, suite, structure verdict>
FILES: <changed paths, or none>
ORACLE: <the last verification command> => exit <n>
NEXT: operator
ASK: <only when STATUS is not done>
```

Good: `SUMMARY: dry4py clean; ruff clean; suite green; no structural change`
Bad: `SUMMARY: looks good`

`NEXT` names the role the orchestrator dispatches next (`operator` ends the run). The architect
never calls it; to request a fix, put the role and the fix in the message and let the orchestrator
dispatch.
