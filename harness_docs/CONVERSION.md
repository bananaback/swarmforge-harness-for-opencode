# SwarmForge to OpenCode Conversion

Distillation of Uncle Bob's SwarmForge workflow into an opencode-native four-role
pack. Same communication spirit, none of the tmux machinery.

## Current State

Conversion is complete; the harness root is clean (no `test/` or
`tmp/`). SwarmForge-derived pieces live under `swarm-forge-tin/`; the harness
files stay at the root. A new session can start from these artifacts:

| Artifact | Purpose |
|---|---|
| `AGENTS.md` | Distilled constitution: Mail Protocol, dispatch rules, engineering rules |
| `.opencode/agents/*.md` | The four role prompts: specifier, coder, refactorer, architect |
| `.opencode/tools/mail.ts` | `mail_send`, `mail_pull`, `mail_done`, `mail_status` tools |
| `swarm-forge-tin/tools/mailbox.py` | Deterministic mailbox core and CLI; the validation boundary |
| `swarm-forge-tin/tools/aps/` | Vendored Acceptance-Pipeline-Specification Babashka source, unmodified; Go fallbacks pruned |
| `swarm-forge-tin/tools/gherkin-parser`, `ir-dry-checker`, `gherkin-mutator` | Wrappers executing the vendored APS bb tasks |
| `swarm-forge-tin/tools/crap4py` | CRAP wrapper: coverage.py LCOV + radon cyclomatic complexity, crap4clj formula and report shape |
| `swarm-forge-tin/tools/dry4py` | Duplicate-code wrapper over jscpd 5; JSON report into `swarm-forge-tin/dump/dry4py/` |
| `swarm-forge-tin/tests/` | Empty test template: `features/`, `acceptance/`, `unit/`, `property/`, `tools/`, `fixtures/`, plus `pytest.ini` and `conftest.py`; roles fill it as they work |
| `swarm-forge-tin/dump/` | Reproducible tool artifacts; safe to clean with `rm -rf swarm-forge-tin/dump/*` |
| `opencode.json` | Global model config; per-agent models live in agent frontmatter |
| `swarm-forge-tin/ruff.toml` | Ruff config; pins the cache under `swarm-forge-tin/dump/ruff-cache` |
| `swarm-forge-tin/tools/ruff4py` | Code-quality wrapper: `ruff check` with the cache pinned under `swarm-forge-tin/dump/` |
| `swarm-forge/` | Upstream reference clone, read-only source of truth |

## Principle

Keep the deterministic invariants:

- Queue state lives in the filesystem; location is the state.
- Only tools move mail; agents never hand-edit queue state.
- Every transition is one atomic operation (`rename`); writes are temp + rename.
- Priority ordering, stable task names, idempotent retry by content hash.
- Wake-ups are lossy; the durable mailbox is the source of truth.

Drop the transport:

- No tmux, no send-keys, no handoff daemon, no polling.
- No worktrees and no git commit as the handoff pivot.
- No dashboard; the operator and opencode sessions are the control plane.

## Mapping

| SwarmForge | This workspace |
|---|---|
| tmux pane + `send-keys` wake | opencode subagent dispatch (`task`); dispatch is the wake |
| `handoffd` daemon delivery | none; `mail_send` fans out atomically on the spot |
| `swarm_handoff.sh` | `mail_send` |
| `ready_for_next.sh` | `mail_pull` |
| `done_with_current.sh` | `mail_done` |
| `merge_and_process.sh` | not ported; all roles share one project directory |
| `git_handoff` (commit pivot) | `handoff`; commits are optional and manual |
| `note` | `note` (one line, max 80 chars, only when directed) |

## Steps Done

1. Reference clone: `swarm-forge/` upstream read-only source of truth.
2. Constitution distilled: `AGENTS.md`.
   - `# Handoff Rules` replaced by `# Mail Protocol` (`mail_*` tools only,
     wake line, forward chain, verification handoffs).
   - `# Worktree Discipline` replaced by `# Workspace` (one shared directory).
   - Commit optional: handoffs never wait for, require, or reference a commit.
   - Removed nonexistent `swarm_tool.sh` references from Language Defaults and
     Acceptance Pipeline; stale `swarm_tool.sh` bash deny patterns removed from
     role prompts.
3. Role prompts: `.opencode/agents/{specifier,coder,refactorer,architect}.md`.
   - `mode: all`, per-role model and permissions.
   - `edit: {".swarmforge/**": deny}` so agents cannot write queue state.
   - Handoff sections use `mail_send` / `mail_pull` / `mail_done`.
   - The specifier's first-hop `mail_done` is conditional: a role dispatched
     with a task instead of inbound mail holds no in-process item.
4. Mailbox core: `swarm-forge-tin/tools/mailbox.py` (stdlib only).
   - States `new -> in_process -> completed` (+ `failed`) under
     `.swarmforge/mail/inbox/<role>/`.
   - Atomic claim by `os.replace`, `flock` single-writer per role and per send,
     content-hash idempotency, priority filenames
     (`<NN>_<timestamp>_<seq>_from_<sender>.json`).
   - Task/batch modes, resume of in-process work, terminal multi-recipient.
   - Session-owned in-process items: only the claiming session can resume or
     complete; a second session is refused, with explicit `takeover` for a
     dead owner. `mail_status` shows the holder and how long it has held.
   - No TTL or heartbeat. A hung owner blocks only that item until the operator
     confirms the session is stopped; the tool never expires an owner on its
     own. Takeover is operator-directed only; refusal messages tell the agent
     to ask the operator.
   - Interrupted tool calls are safe: transitions are atomic, so a `pull` or
     `done` either happened or did not. The same session can re-run `mail_pull`
     without takeover; a replacement session needs `takeover: true`.
5. OpenCode tool adapter: `.opencode/tools/mail.ts`.
   - Tools `mail_send`, `mail_pull`, `mail_done`, `mail_status`.
   - Sender identity from `context.agent`, session from `context.sessionID`;
     agents cannot spoof or forget it.
   - Shell adapter calls the Python CLI; the CLI is the validation boundary.
   - Tool modules load when the opencode server starts; after editing
     `.opencode/tools/*.ts`, restart before relying on the change. Queue state
     is durable, so a restart never loses mail.
6. Verification: high-volume stress runs proved concurrent send no-loss,
   concurrent pull single-claim, crash resume, idempotent send/done, batch
   claim/resume, priority order, validation errors, and torn-file safety.
   Scratch folders used during conversion were removed to keep the harness
   root clean.
7. Config: `opencode.json` (global model) plus per-agent model frontmatter.
8. Gherkin acceptance tools: the APS Babashka source is vendored unmodified at
   `swarm-forge-tin/tools/aps/` (`bb.edn`, `bb/`, and the spec documents); Go
   fallbacks are pruned. Wrappers `swarm-forge-tin/tools/gherkin-parser`,
   `ir-dry-checker`, and `gherkin-mutator` exec
   `bb --config swarm-forge-tin/tools/aps/bb.edn <task>`. The mutator wrapper
   keeps the author's guard: it always passes `--workers 4` and converts
    `--level full` to `--level hard`. Reproducible artifacts, including parse IR,
    dry reports, and mutation work dirs, go under `swarm-forge-tin/dump/`.
9. Layout: SwarmForge-derived pieces (mailbox, APS, wrappers, dump) live under
   `swarm-forge-tin/`; the harness files (`.opencode/`, `AGENTS.md`,
   `opencode.json`, `CONVERSION.md`) stay at the root. The upstream reference
   clone stays at `swarm-forge/`.
10. Coder tooling smoke-verified for a Python project (scratch project under
    `./tmp/`, removed after). pytest 9.1.1 is installed globally; pytest plus
    the vendored `gherkin-parser` are the coder's only external tools. The full
    coder pipeline was exercised: feature -> `gherkin-parser` IR -> a
    project-specific acceptance entrypoint generator + runtime + regex step
    handlers built to the APS contracts -> generated pytest entry points with
    `metadata/<feature>.json` and `implementation_hash`. Every acceptance
    component is project code the coder writes; no install.
11. Coder prompt `.opencode/agents/coder.md` now teaches the vendored APS
    contracts (`parser-spec.md`, `acceptance-generator.md`), the generated
    entrypoint requirements (embed/load IR, run all executions, delegate to
    handlers, deterministic), and the Python rule: `python3 -m pytest` for unit
    and generated acceptance tests, plain and non-interactive.
12. Refactorer tooling settled for Python. Installed globally: coverage.py
    7.15.4, radon 6.0.1, hypothesis 6.168.0 (pip), jscpd 5.2.0 (npm). Wrappers
    `swarm-forge-tin/tools/crap4py` (coverage.py LCOV + radon CC, crap4clj
    formula, module filters, `--use-existing-coverage`) and
    `swarm-forge-tin/tools/dry4py` (jscpd with fixed defaults, `--workers 4`,
    text clone pairs, JSON in `swarm-forge-tin/dump/dry4py/`). Conversion-time
    smoke runs exercised the full refactorer loop, CRAP reduction after
    extracting a shared `apply_tax`, and legacy behavior: partial coverage
    marks unmeasured functions N/A, a pre-existing failing test and a
    syntax-broken file only produce warnings, `--test-path` scopes the test run
    to the module under work, and `--ignore` keeps legacy trees out of the DRY
    scan. Mutation testing is intentionally not part of the Python workflow.
    `AGENTS.md` now has a Python row in the language table;
    `.opencode/agents/refactorer.md` names the wrapper commands.
13. Test root template: `swarm-forge-tin/tests/` holds the layout roles write
    into: `features/` (Gherkin), `acceptance/` (generated entrypoints, runtime,
    step handlers), `unit/`, `property/`, `tools/`, and `fixtures/`, plus
    `pytest.ini` and `conftest.py`. Artifacts stay separate: coverage data,
    LCOV, jscpd reports, pytest cache, hypothesis database, ruff cache, and
    test work dirs all land under `swarm-forge-tin/dump/`, and
    `PYTHONDONTWRITEBYTECODE=1` keeps bytecode out of source trees. `crap4py`
    defaults its LCOV and `COVERAGE_FILE` under `dump/` and runs pytest with
    `-p no:cacheprovider`; `dry4py` honors `--report` names and `--ignore`
    globs. The four role prompts and `AGENTS.md` route tests to
    `swarm-forge-tin/tests/` and keep the project source tree test-free.
14. Architect tooling settled and mutation removed: `.opencode/agents/architect.md`
    runs `swarm-forge-tin/tools/ruff4py`, then `dry4py`, then the test suite
    (property tests as a separate explicit command); the language mutation
    tool, `gherkin-mutator`, and the runner adapter are gone from the prompt.
    `AGENTS.md` adds `ruff` to the Python language row and removes mutation
    from Startup Tools, the acceptance pipeline, Verification, and Guardrails.
    Ruff 0.16.6 is installed; the `swarm-forge-tin/tools/ruff4py` wrapper
    pins its cache under `swarm-forge-tin/dump/ruff-cache`.
15. Fresh-start reset: every conversion-era test and fixture was removed from
    `swarm-forge-tin/tests/` so the pack can be exercised end to end on a new
    sample feature. The test root now holds only the empty template layout,
    `pytest.ini`, and `conftest.py`; `swarm-forge-tin/dump/` holds only
    `.gitkeep`. The tools under `swarm-forge-tin/tools/` are untouched.

## Operational Loop

1. Operator or master checks `mail_status` and dispatches a role with
   `MAIL_WAITING: run mail_pull`.
2. Role runs `mail_pull`, processes the printed `PAYLOAD`.
3. Role runs `mail_send` to the next role, then `mail_done`.
4. `mail_done` prints `MAIL_WAITING` if more mail is queued; pull again, else
   stop. The dispatcher wakes the next role on the next hop.

One session per role at a time; duplicate dispatch is refused by ownership, not
by a lock. If a session hangs or stops, the operator stops it with ESC (the
session shows an interrupted tool call). The same session may re-run
`mail_pull`; otherwise the operator dispatches a replacement with
`takeover: true`. Liveness is always an operator decision.

## Verify

Tool script parses:

```sh
node --experimental-strip-types --check .opencode/tools/mail.ts
```

Smoke test in a throwaway root, removed afterwards:

```sh
root=$(mktemp -d)
mkdir -p "$root/.opencode/agents"
for r in specifier coder refactorer architect; do
  printf -- "---\ndescription: smoke role\n---\n" \
    > "$root/.opencode/agents/$r.md"
done
python3 swarm-forge-tin/tools/mailbox.py --root "$root" send \
  --from specifier --to coder --task feature-1
python3 swarm-forge-tin/tools/mailbox.py --root "$root" pull --as coder
rm -rf "$root"
```

Vendored APS suite:

```sh
bb --config swarm-forge-tin/tools/aps/bb.edn test
```

Tests are created per feature by the coder; run them as:

```sh
cd swarm-forge-tin/tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
```

Gherkin smoke test in the dump folder, removed afterwards:

```sh
printf 'Feature: Demo\n\n  Scenario: Example\n    Given a value of 1\n    Then the result is 1\n' > swarm-forge-tin/dump/demo.feature
swarm-forge-tin/tools/gherkin-parser swarm-forge-tin/dump/demo.feature swarm-forge-tin/dump/demo.json
swarm-forge-tin/tools/ir-dry-checker swarm-forge-tin/dump/demo.json swarm-forge-tin/dump/demo.dry.json
rm -f swarm-forge-tin/dump/demo*
```

Clean every reproducible tool artifact with `rm -rf swarm-forge-tin/dump/*`. Never delete `swarm-forge-tin/tests/`; the roles build their persistent tests there.

## Open Items

- Two-call audit gate from `handoff-protocol.md` not ported; add if wanted.
- Optional plugin auto-wake via `session.idle` not needed while dispatch is the
  wake; keep mail pulls pointer-only if added.
- CRAP and DRY tools are independent of the mail transport. APS tools are
  vendored at `swarm-forge-tin/tools/aps/`.
- Python tooling is chosen and provisioned (see Steps Done 12): coverage.py,
  radon + `crap4py`, jscpd + `dry4py`, hypothesis, pytest, ruff. Mutation
  testing is intentionally omitted. The architect's verification runs
  `swarm-forge-tin/tools/ruff4py`, `dry4py`, and the test suite; no runner
  adapter or Gherkin mutation.
- `prompting-guide.md` is reference material only, not part of the pack.
