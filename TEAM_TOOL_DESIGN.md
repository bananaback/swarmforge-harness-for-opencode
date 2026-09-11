# Team Tool — Deterministic Session Routing for the MiMo / V4 / V4.1 Triple

**Captured:** 2026-09-11
**Status:** design captured, not implemented (deprioritized behind a priority task)

## 1. Purpose

The existing mail tool routes by agent name: a sender leaves durable mail, the orchestrator dispatches the role, and the summoned agent reads only its own mailbox. Deterministic, no racing, single source of truth.

The MiMo/V4/V4.1 triple needs the same strength, but its members are per-chunk sessions, not global roles. If the worker had to remember mentor/senior task ids, it could hallucinate them and spawn the wrong sessions. This note specifies a new tool (`team`) that owns the seat→session binding so no model ever handles a session id.

## 2. Principles

1. The durable box is the source of truth; a dispatch is a lossy wake that carries nothing.
2. Routing key is `(chunk, seat)`, never an agent-chosen session id.
3. One in-process item per seat; atomic claims; no racing.
4. The worker (W) is spawned eagerly at chunk open; the mentor (M) lazily on W's first ask; the senior (S) lazily on M's first escalation.
5. Once spawned, every session is bound to the chunk until it ends, then all are abandoned together. No session is reused across chunks; no session dies early.
6. The oracle is the only source of green; test files are hash-pinned.
7. No rollback machinery: the operator does not commit frequently; recovery means continue from the current tree, not restore green.

## 3. Lifetime

```
orchestrator dispatch = chunk C
│
├── W  MiMo worker   sid_W   spawned at open
├── M  V4 mentor     sid_M   spawned on W's first ask
└── S  V4.1 senior   sid_S   spawned on M's first escalation

        all bound to C for C's entire life; abandoned together when C ends
        next chunk → brand-new triple, fresh session ids, no carryover
```

- The roster is a stub at open: `{ chunk: C, W: sid_W, M: —, S: — }`, filled lazily.
- A message to an unbound seat sets `SPAWN_PENDING`; the orchestrator spawns, binds, wakes.
- Once bound, every later message resolves to that session. Re-binding requires operator-confirmed takeover.

## 4. Minimal operations (7)

CONTROL — orchestrator only

| op | effect |
|---|---|
| `team_open C [--brief REF]` | create roster + seed worker@C with the chunk item |
| `team_bind C SEAT SID` | atomic; refuse if bound (`--takeover` = operator-confirmed replacement) |
| `team_status C [--ready]` | read: bound/unbound seats, queue counts, in-process holder, SPAWN_PENDING |
| `team_close C` | seal chunk; refuse further sends/pulls |

DATA — bound seats only

| op | effect |
|---|---|
| `team_pull [--seat HINT]` | claim/resume my in-process item; resolves caller → seat → box |
| `team_send --to SEAT --kind K --message M` | enqueue into target seat's box in MY chunk |
| `team_done` | complete my item; prints READY if more queued |

Kinds and edges are fixed and tool-enforced:

| edge | allowed kind |
|---|---|
| worker → mentor | ask |
| mentor → worker | brief |
| mentor → senior | escalate |
| senior → mentor | decision |

Models name only the target seat. The chunk comes from the caller's binding; session ids never appear in model context.

## 5. Wake contract

Constant line, zero payload:

```
TEAM_WAITING: run team_pull
```

Same for every seat, every chunk, first spawn and re-wake. All content comes from `team_pull`. Content in a dispatch means two sources of truth (prompt vs durable record), truncation/drift/replay bugs, and an injection surface — rejected.

## 6. Flow

### Normal ask cycle

```
t0  O: team_open C --brief dump/C/brief.md   → worker@C box: chunk item
    O: spawn W → team_bind C worker sid_W    → roster: W bound
    O: wake W                                 ("TEAM_WAITING: run team_pull")

t1  W: team_pull                              → chunk item (brief, allowlist, oracle cmd)
    W: edit → oracle → edit → oracle (red ×2, same signature)
    W: team_send --to mentor --kind ask --message "attempt 2 red, sig 9f2c; brief says
         None, oracle line 42 wants ValueError"
    W: team_done                              → COMPLETED; NO_TASK
       tool: mentor@C queued, mentor unbound → SPAWN_PENDING

t2  O: team_status C --ready                  → "mentor: SPAWN_PENDING"
    O: spawn M → team_bind C mentor sid_M
    O: wake M

t3  M: team_pull                              → the ask
    M: team_send --to worker --kind brief --message "raise ValueError; loader catches it;
         one file: src/schedule/dateparse.py"
    M: team_done                              → COMPLETED; NO_TASK
       tool: worker@C queued

t4  O: team_status C --ready                  → "worker: queued"
    O: wake W (sid_W)

t5  W: team_pull                              → brief; edit; oracle green
    W: mail_send forward handoff (four-role pipeline, feature name)
    W: team_done

t6  O: team_close C                           → abandon W, M; drop roster
```

### Escalation branch

```
t3' M: team_send --to senior --kind escalate --message "boundary: loader except clause
         must change to catch ValueError"
    M: team_done
    O: team_status C --ready                  → "senior: SPAWN_PENDING"
    O: spawn S → team_bind C senior sid_S → wake S

t4' S: team_pull                              → the escalate
    S: team_send --to mentor --kind decision --message "approved: catch ValueError;
         no interface change"
    S: team_done
    O: wake M (sid_M)

t5' M: team_pull → decision
    M: team_send --to worker --kind brief --message "…"
    M: team_done
    O: wake W
```

### Who ever calls what

```
W:  team_pull · team_send(ask) · team_done
M:  team_pull · team_send(brief | escalate) · team_done
S:  team_pull · team_send(decision) · team_done
O:  team_open · team_bind · team_status · team_close

Models never pass: chunk id, own seat, session id.
The chunk comes from the caller's binding; the box from the binding; the target seat is
the only thing a model names, and only on the four allowed edges.
```

## 7. Loop policy

| step | cap | stop early |
|---|---|---|
| MiMo tries | 3 | same failure signature twice in a row |
| Ask to mentor | 1 | — |
| MiMo tries after brief | 2 | — |
| Mentor takes over chunk | 1 run | — |
| Senior | 1 run | only interface/boundary/terminal |
| Chunk fails | — | report to operator |

Ask package (what M receives on `team_pull`): attempt number, brief version, raw oracle tail reference, diff stat, failure signature, ONE concrete question. No attempt history, no self-narrative. The raw tail lives in `dump/<chunk>/last-fail.txt`; mail stays a pointer.

Ask only for: a brief/oracle contradiction; input outside the allowlist; a concrete decision with options. Never "is my code correct?" — the oracle answers that.

## 8. Failure / resume

| case | behavior |
|---|---|
| worker dies mid-chunk | operator confirms → replacement binds to the worker seat (`--takeover`); box unchanged; continues from the current tree |
| mentor dies | same; the box belongs to the seat, so no mail is lost |
| senior dies | same; nothing to replay |
| chunk ends red | no rollback; report to operator; abandon the triple |
| test file touched | hard stop; zero tolerance; report to operator |
| stale session pulls after rebind | refused (not the bound session) — fencing for free |
| orchestrator restarts | `team_status` reads durable bindings/boxes; unknown seat → operator-confirmed spawn + bind |
| double dispatch | second bind refused; duplicate session stopped |

## 9. Why it is strong

- Deterministic resolution: `(C, mentor)` → `sid_M` or `SPAWN_PENDING`; never model-chosen.
- No racing: atomic bind; one in-process item per seat.
- No hallucination surface: session ids never enter model context.
- Fencing free: the binding table rejects stale sessions; no epochs needed.
- Crash-safe: boxes belong to seats, not sessions.
- Restart-safe: bindings and boxes are durable on disk.

## 10. Implementation notes

- Works cleanly as an opencode plugin: the runtime hands the tool the caller's session id, so `team_pull` / `team_send` / `team_done` need no identity arguments.
- CLI fallback: no caller identity; use a per-session token written at bind time (env var, or a file only that session reads). `--seat` is a hint, validated against the binding. Raw session ids still never enter model context.
- Spawn ownership: the tool never creates sessions (the state machine stays pure); the orchestrator spawns and binds. If a later plugin can create sessions, it can fulfill `SPAWN_PENDING` itself.

## 11. Mentor context and caching

- The mentor session lives only for the chunk (same life as W), so its context is the chunk: a stable prefix written once (system, spec, frozen interfaces, step plan, decision table) plus appended deltas (asks, briefs, escalations).
- The same session serves every mentor dispatch within the chunk, so the prefix cache hits; volatile values are appended last.
- No cross-chunk memory by design; each chunk pays its prefix once.

## 12. Research grounding

- Coverage from cheap-model sampling pays only with an external verifier (Large Language Monkeys) → the loop runs only where tests verify, and every iteration consumes a fresh oracle signal.
- Intrinsic self-correction without external feedback degrades (Huang et al.) → no "think again" attempts; ask instead.
- Escalation is optimal stopping; the strongest trigger is information stagnation (Self-escalation; TACIT-Switch) → stop on the same signature twice, not on attempt count alone.
- Gate per step with an independent verifier; a producer is not its own judge (Hallucination Snowball; MAST) → the oracle is the only green; the mentor only advises.
- Rollback beats retry-on-mess (Spark to Fire) → failed diffs and narrative never travel; containment here is the small allowlist plus the chunk budget, since there is no commit checkpoint.

## 13. Rejected alternatives (do not re-litigate)

- Message content inside the dispatch/wake → two sources of truth; rejected.
- Pre-spawning M and S at chunk open → wasted sessions; rejected.
- Rollback to last green / commit checkpoints → the operator does not commit frequently; rejected.
- Epochs / fencing tokens → the binding table already fences stale sessions; rejected.
- A long-lived mentor across chunks → violates the one-chunk lifetime; rejected.
- MiMo remembering mentor/senior task ids → hallucination surface; rejected.
- Role-name routing for the triple → roles are global, seats are per-chunk; a new tool is required.

## 14. Open questions

- Plugin vs CLI (how the tool learns the caller's session identity).
- Budget enforcement locus (tool vs harness wrapper).
- Plan-time routing (`v4-led` / `v4.1-led` chunks) — deferred; v1 is `mimo+ask` only.
- Chunk brief location (`dump/<chunk>/brief.md` proposed).

## 15. Context engineering

### Model

```
pack      sealed at team_open, never edited        → stable prefix, cache hits
journal   append-only, worker-authored only        → the worker's thinking, as it works
cursor    per seat: how far that seat has watched  → context calls deliver the delta
```

### Pack (assembled by the orchestrator at open, sealed)

| file | content |
|---|---|
| `brief.md` | chunk objective, problem statement |
| `plan.md` | allowlist, oracle command, done criteria, budgets |
| `interfaces.md` | frozen signatures + call sites |
| `decisions.md` | decision table + decisions carried in |
| `refs.md` | spec excerpt, feature/IR/acceptance paths |

Hash recorded at open; an edited pack is a protocol error and the pull is refused.

### Delivery

| op | caller | effect |
|---|---|---|
| `team_context` | seat | first call: pack + journal[0..now]; sets `loaded=true`, `cursor=now` |
| `team_context --delta` | seat | journal[cursor..now]; advances cursor |
| `team_journal` | worker | append one entry (see §16) |

Rules: `--delta` with `loaded=false` → `LOAD_REQUIRED`. `team_bind` / `--takeover` resets `loaded=false`, `cursor=0`. Dialogue (ask/brief/escalate/decision) is never delivered by context — it lives in the advisors' session turns. Journal entries carry the evidence (failure sections, diffs); bulk raw output and artifacts stay as refs.

### Bounds

pack ≤8 KB. Worker journal prose is uncapped — detail is paid once, unclear context is paid every attempt. Failure sections and diffs are inlined; only bulk raw output and artifacts stay as refs. Deltas follow the journal; no size cap. No compaction within a chunk: decision records are never dropped or summarized.

### Directory

```
swarm-forge-tin/.swarmforge/team/<chunk>/
  roster.json      bindings + cursors
  pack/            sealed at open
  journal.jsonl    worker-authored, append-only
  attempts/        NN.tail.txt · NN.diff · NN.json   (evidence, not journal)
```

## 16. Journal design (final)

### Axiom

Journal detail is paid once; unclear context is paid every attempt. Never trade journal length for tokens.

### Rule

The journal is the worker's thinking only. The harness has no thinking, so it writes no journal entries; its facts are attached to the worker's entries from attempt artifacts. Dialogue is not journaled; it is already in the advisors' session turns.

### Four kinds

| kind | carries | when |
|---|---|---|
| `readback` | goal, constraints, done, understanding | once at chunk start |
| `plan` | full decision record | before a distinct approach |
| `result` | full evidence + reading | after each oracle run |
| `note` | lessons that survive the chunk | rarely |

### `plan` — full decision record (prompts, not limits)

```
situation    where we are, what triggered this decision
options      A/B/C… each with: description, for (evidence), against (evidence)
choice       the pick
rationale    full reasoning — which brief/spec/test lines drive it, what the protocol says,
             why this option first, what the attempt buys even if it fails
assumptions  what must be true for this to work
uncertainties what is unresolved, and what would resolve it
falsifiers   what result rejects this choice
change       the intended code change (file, function, shape)
expect       specific observable outcomes, per test
```

### `result` — full evidence + full reading

```
cmd / cwd / exit
failures     every failing test: file:line, assert expression, E lines, got value
change       the actual diff, or the changed function if the diff is huge
trust        tests unchanged · files = allowlist · oracle scope full
observations what happened, step by step
reading      which assumptions held or broke, what is now believed, what is still open
refs         full output / tail / diff artifacts
```

### Rules

- Worker prose is uncapped. Fields are prompts, not limits.
- Facts are attached by the tool from the attempt artifact; `reading` is worker-authored.
- Failure sections and diffs are inlined; only bulk raw output and artifacts stay as refs.
- Never: dialogue duplication, harness-authored entries, self-assessment ("confident", "done") — the harness owns outcomes.

### Example

See `TEAM_JOURNAL_EXAMPLE.md` for a full-depth sample (3 attempts, one ask, one brief, green).
