# refactorer

The refactorer's final message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
SUMMARY: <one line: files touched; max CRAP, DRY, coverage; suite state>
FILES: <created or changed paths>
ORACLE: <the verification command> => exit <n>
NEXT: architect
ASK: <only when STATUS is not done>
```

Good: `SUMMARY: src/cart.py; CRAP max 6, DRY clean, unit+acceptance green`
Bad: `SUMMARY: cleaned up`

`NEXT` names the role the orchestrator dispatches next. The refactorer never calls it.
