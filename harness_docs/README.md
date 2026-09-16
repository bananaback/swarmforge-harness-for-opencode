# SwarmForge Harness — Docs

SwarmForge turns operator intent into shipped behavior through a four-role
opencode pipeline (`specifier → coder → refactorer → architect`), each phase
gated by tests and advised by a mentor. The `swarm-forge-tin/` pack is the
harness that runs the pipeline, and it points at this repository itself
(self-hosting).

## The System At A Glance

```
operator intent
      │
      ▼
orchestrator ──dispatch──► specifier ──.feature──► coder ──► refactorer ──► architect
   (control plane)              │            mail is the durable task chain
                                │
        every coder/refactorer/architect dispatch also runs a phase chunk:
                     worker seat (the role) ◄──ask/brief──► mentor seat
                     oracle = the chunk's test command
```

- **Harness pack** (`swarm-forge-tin/`): config, CLIs, tests, generated areas.
- **Wiring** (`harness.json`): every path the tools and roles use, resolved once.
- **State**: durable mail and per-task chunks under `.swarmforge/`.
- **Acceptance pipeline**: Gherkin → JSON IR → generated pytest entry points,
  plus spec mutation.

## Docs

| Doc | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Wiring/config, pack layout, test areas, durable store, task/chunk state, journal |
| [TOOLS.md](TOOLS.md) | `mailbox` and `team` operation reference, context payload contracts, opencode bridges |
| [WORKFLOW.md](WORKFLOW.md) | Roles, model routing, dispatch loop, phase chunks, handoffs, recovery |
| [INTEGRATION.md](INTEGRATION.md) | Point the pack at any project: one config, pack-vs-project tests, switching, leak-free wiring |
| [TESTING.md](TESTING.md) | Test areas, persistence policy, acceptance pipeline, spec mutation, quality gates |
| [ROADMAP.md](ROADMAP.md) | Current status, milestone table, backlog, resume checklist |
| [examples/](examples/) | Annotated coder payload, mentor payload, and worker journal |
| [prompting-guide.md](prompting-guide.md) | Prompting techniques for agent-prompt work |

`AGENTS.md` at the repo root is the constitution (engineering rules); it stays
there by convention.

## Repository Map

```
harness_research/
├── AGENTS.md, opencode.json, .gitignore      constitution + opencode config
├── harness_docs/                             this documentation
├── .opencode/                                agent pack (8 agents, tool bridges, autobind)
└── swarm-forge-tin/                          the harness pack
    ├── harness.json                          wiring config (self-pointing)
    ├── ruff.toml
    ├── tools/                                harness CLIs + vendored APS tools
    ├── harness_tests/persistent/             harness self-tests (committed)
    ├── project_tests/persistent/             wired-project tests, pack-side (committed)
    ├── hot_tests/                            generated tests (gitignored, disposable)
    └── dump/                                 reports and caches (gitignored, disposable)
```

Full tree: [ARCHITECTURE.md § Repository Layout](ARCHITECTURE.md#repository-layout).

## Quick Start

```bash
# resolved paths (never hardcode pack paths)
swarm-forge-tin/tools/harness status

# harness self-tests
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# acceptance pipeline (parse -> dry -> generate -> run)
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py

# quality gates
swarm-forge-tin/tools/ruff4py swarm-forge-tin/tools swarm-forge-tin/harness_tests/persistent
swarm-forge-tin/tools/crap4py --source-root swarm-forge-tin/tools \
  --test-path swarm-forge-tin/harness_tests/persistent
swarm-forge-tin/tools/dry4py --min-lines 4 swarm-forge-tin/tools
```

## Design Decisions (Do Not Re-litigate)

- All eight agents run `opencode-go/deepseek-v4.1-flash`, variant `high`.
  Changing a model or agent config needs an opencode restart.
- No senior tier; no ask or attempt caps. The worker/mentor pair talk until the
  oracle is green; the mentor owns boundary calls directly.
- Plan-time routing (`v4-led` / `v4.1-led` chunks) is deferred.
- Rejected alternatives: message content in the wake line; pre-spawning the
  mentor; rollback checkpoints; epochs/fencing tokens; a long-lived mentor; a
  model holding session ids; role-name routing for the pair.

Known limitations are in
[ARCHITECTURE.md § Known Limitations](ARCHITECTURE.md#known-limitations).
