# SwarmForge Lite — Minimal Specifications

Lite keeps the TDD discipline and drops the orchestration machinery. The
workflow is still `specifier → coder → refactorer → architect`; the transport is
structured output, not a stateful mail/team queue. The goal is light speed and
parallel subagents without spinning up a machine to move a note.

## Principles

1. **Simplicity first.** The smallest tool that works; every line earns its
   place.
2. **Structured output is the interface.** A role's result is a schema-checked
   document, not a queue state machine.
3. **Parallel by disjoint ownership.** Chunks that touch different files run at
   the same time.
4. **Keep the gems; drop the overhead.** The acceptance pipeline and the quality
   wrappers stay; the mail/team/autobind stack goes.
5. **The discipline is unchanged.** No role certifies its own work.

## Tool Inventory

| Tool | Fate |
|---|---|
| `gherkin-parser`, `ir-dry-checker`, `gherkin-mutator` (vendored APS) | **keep as-is** |
| `crap4py`, `dry4py`, `ruff4py` | **keep**; refactor later |
| `harness.py` (`config` / `status` / `clean`) | **keep**; refactor later |
| `mailbox.py`, `team.py`, `durable_store.py` | **drop** |
| `.opencode/tools/mail.ts`, `team.ts`, `team-autobind` plugin, `lib/wiring.ts` | **drop** |
| `specifier`, `coder`, `refactorer`, `architect` | **keep** |
| `orchestrator` | **keep**, simplified to spawn-and-read |
| transport | **new**, ≤ 200 LOC |

## A. Wiring And Layout

**S1. One config.** A single `harness.json` resolves `workspace_root`,
`source_roots`, `persistent_tests`, `features`, `artifacts_root`, `state_root`,
and `hot_tests`. No tool hardcodes a path.
*Check:* `harness.py status` prints every resolved path and exits 0.

**S2. Layout.** Source lives under `source_roots` and stays test-free. Authored
tests live under `persistent_tests/{unit,property,features,acceptance}`.
Generated entry points go to `hot_tests`; reports and caches to
`artifacts_root`.
*Check:* a full run adds no file under `source_roots`.

**S3. Switch by config.** Repointing the pack means editing the config and
running `harness.py clean hot`.
*Check:* after a switch, no generated entry point from the prior project
remains in `hot_tests`.

## B. Transport (Minimal)

**S4. Structured handoff.** A handoff is one JSON document. Required fields:
`task`, `from`, `to`, `seq`, `summary`. Optional: `files`, `oracle`, `exit`.
A missing required field or an unknown role is refused.
*Check:* an invalid handoff exits 2 and writes nothing.

**S5. Append-only and lock-free.** Handoffs are numbered files under the task's
state directory; a writer only creates a new file, never edits an old one.
Concurrent writers to distinct files do not block each other.
*Check:* two handoffs written concurrently both exist with distinct `seq`.

**S6. Tiny surface.** The transport CLI does `send`, `read`, and `status` only,
and keeps its logic under 200 lines.
*Check:* `read` renders a task's handoffs in `seq` order.

## C. Pipeline

**S7. Specification first.** The specifier writes deterministic Gherkin under
the features root; each scenario carries a stable name/index; every
example-table column is load-bearing. It parses with `gherkin-parser` and
dry-checks with `ir-dry-checker`.
*Check:* parse and dry-check exit 0; no column is constant across all rows.

**S8. Approval gate.** The specifier asks the operator (`question` tool:
`Approve` / `Request changes` / `Stop`) and hands off only after approval.
*Check:* a `Request changes` produces a revised feature before any handoff.

**S9. Decompose.** One plan splits the feature into chunks; each chunk carries
`task`, `role ∈ {coder, refactorer, architect}`, a brief, an interface contract,
an `oracle` command, and a file allowlist. Allowlists are pairwise disjoint.
*Check:* no path appears in two chunks; every chunk has an oracle.

**S10. TDD loop.** The coder writes a focused failing unit test first, then the
smallest production code to pass. The chunk's oracle is the pinned command and
the only source of green; the coder never edits the tests or the oracle to pass.
*Check:* the first oracle run is red for the expected reason before edits.

**S11. Acceptance pipeline.** Generated entry points embed the IR and delegate
to the runtime and step handlers; they never re-parse the feature. One handler
per repeated step shape; the runtime refuses a duplicate or ambiguous pattern.
*Check:* every feature step resolves to exactly one handler.

**S12. Refactor.** The refactorer changes structure only, never behavior. It
runs CRAP (≤ 10 per function), DRY (0 clones), and coverage, and owns property
tests as a separate run. It runs no mutation.
*Check:* the suite is green before and after; CRAP and DRY pass.

**S13. Architect gate.** The architect runs, one at a time, spec mutation
(`run_mutation.py --level soft`) → DRY → the full suite, fixing each before the
next, and reviews boundaries and dependency direction.
*Check:* no mutant survives; the suite is green.

## D. Verification And Ownership

**S14. No role certifies its own work.** Ownership is fixed:

| Role | May run | May not run |
|---|---|---|
| Specifier | parser, dry-checker | mutation |
| Coder | unit + acceptance tests | CRAP, DRY, mutation |
| Refactorer | CRAP, DRY, coverage, property | mutation |
| Architect | spec mutation, DRY, full suite | the coder's or refactorer's edits |

*Check:* each role's tool permissions match the row.

**S15. Oracle is green.** A chunk's green is accepted only with the oracle
command and its exit code attached to the handoff.
*Check:* a handoff claiming green with no oracle result is refused.

## E. Parallelism And Durability

**S16. Disjoint ownership.** Two chunks with disjoint allowlists may run
concurrently. A chunk never edits outside its allowlist.
*Check:* every edit lands inside the chunk's allowlist.

**S17. Conflict ownership.** When parallel work overlaps anyway, the receiver
resolves the conflict. Conflict resolution is engineering work, not an error.
*Check:* an overlapping edit is reconciled and the suite stays green.

**S18. Durable and minimal.** All state is append-only files under
`state_root`; there are no locks and no daemons. Deleting `hot_tests` or
`artifacts_root` never deletes a persistent test.
*Check:* removing the disposable areas leaves the persistent suite intact.

**S19. Operator in the loop at gates.** Ambiguity or a spec/test conflict is
escalated to the operator, not carried in side chat.
*Check:* an unresolved conflict produces a question, not a silent guess.

## Out Of Scope (Dropped As Overhead)

- wake lines (`MAIL_WAITING` / `TEAM_WAITING`) and content-free dispatch
- mail queue states, in-process ownership, takeover, batch mode
- session→seat binding, `SPAWN_PENDING`, `team-autobind`
- deterministic role payloads
- journal kinds, attempt artifacts, oracle-change records, delivery cursors
- per-role mail locks and per-task team locks
- the `team_open` bridge; the plan is consumed directly
