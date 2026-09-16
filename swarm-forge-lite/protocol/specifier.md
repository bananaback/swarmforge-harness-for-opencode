# specifier

The specifier's final message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
SUMMARY: <one line: feature path, the behavior pinned, IR/dry state, operator approved>
FILES: <feature path, IR path, dry path>
NEXT: coder
ASK: <only when STATUS is not done>
```

Good: `SUMMARY: login.feature; one behavior per scenario; IR parsed, dry clean; operator approved`
Bad: `SUMMARY: wrote a spec`

`NEXT` names the role the orchestrator dispatches next. The specifier never calls it.
