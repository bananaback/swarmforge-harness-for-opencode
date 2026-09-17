# specifier

The specifier's final message.

```
TASK: <stable task name>
STATUS: done | blocked | needs-input
APPROVED: yes | no
SUMMARY: <one line: feature path, the behavior pinned>
FILES: <feature path, IR path, dry path>
ORACLE: <parse + dry-check command> => exit <n>
NEXT: coder
ASK: <only when STATUS is not done>
```

Good: `STATUS: done`, `APPROVED: yes`, `SUMMARY: login.feature; one behavior per scenario`, `ORACLE: gherkin-parser ... && ir-dry-checker ... => exit 0`
Bad: `SUMMARY: wrote a spec`

`APPROVED: yes` means the operator answered `Approve` at the `question` gate; the orchestrator
dispatches the coder only then. On `Request changes`, revise and re-ask; on `Stop`, report and stop.

`NEXT` names the role the orchestrator dispatches next. The specifier never calls it.
