# coder

The coder's final message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
SUMMARY: <one line: files touched and the oracle result>
FILES: <created or changed paths>
ORACLE: <the exact oracle command> => exit <n>
NEXT: refactorer
ASK: <only when STATUS is not done>
```

Good: `SUMMARY: src/cart.py, unit/test_cart.py; oracle green (12 passed)` with `ORACLE: ... => exit 0`
Bad: `SUMMARY: done`

`NEXT` names the role the orchestrator dispatches next. The coder never calls it.
