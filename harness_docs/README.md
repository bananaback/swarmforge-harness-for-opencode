# SwarmForge Harness — Docs

SwarmForge turns operator intent into shipped behavior through a four-role
opencode pipeline (`specifier → coder → refactorer → architect`), each phase
gated by tests and advised by a mentor. The `swarm-forge-tin/` pack is the
harness that runs the pipeline, and it points at this repository itself
(self-hosting).

This `README` is the map. Read it first, then the three topic docs.

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

## Reading Order

| Doc | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Wiring/config, pack layout, test areas, durable store, task/chunk state, journal |
| [TOOLS.md](TOOLS.md) | `mailbox` and `team` operation reference, context payload contracts, opencode bridges |
| [WORKFLOW.md](WORKFLOW.md) | Roles, model routing, dispatch loop, phase chunks, handoffs, recovery |
| [TESTING.md](TESTING.md) | Test areas, persistence policy, acceptance pipeline, spec mutation, quality gates |
| [ROADMAP.md](ROADMAP.md) | Current status, milestone table, backlog, resume checklist |

Supporting material:

| Path | What |
|---|---|
| [examples/](examples/) | Annotated coder payload, mentor payload, and worker journal |
| [prompting-guide.md](prompting-guide.md) | Prompting techniques; the standard for agent-prompt work |
| [M9-VALIDATION.md](M9-VALIDATION.md) | M9 branch-integration run log and friction list |

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
    ├── project_tests/persistent/             src-project tests, pack-side (committed)
    ├── hot_tests/                            generated tests (gitignored, disposable)
    └── dump/                                 reports and caches (gitignored, disposable)
```

Full tree: [ARCHITECTURE.md § Repository Layout](ARCHITECTURE.md#repository-layout).

## Quick Start

```bash
# resolved paths (never hardcode pack paths)
swarm-forge-tin/tools/harness status

# harness self-tests (373)
cd swarm-forge-tin/harness_tests && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

# acceptance pipeline (22 features, 156 scenarios -> 229 executions)
python3 swarm-forge-tin/harness_tests/persistent/acceptance/run_acceptance.py

# quality gates
swarm-forge-tin/tools/ruff4py swarm-forge-tin/tools swarm-forge-tin/harness_tests/persistent
swarm-forge-tin/tools/crap4py --source-root swarm-forge-tin/tools \
  --test-path swarm-forge-tin/harness_tests/persistent
swarm-forge-tin/tools/dry4py --min-lines 4 swarm-forge-tin/tools
```

## Status (2026-09-15)

Self-hosting and green:

- Wiring: `harness.json` + `tools/wiring.py` + `.opencode/lib/wiring.ts` +
  `tools/harness` (`config` / `status` / `clean`).
- State: dated task/chunk layout with append-only journals and write-once inputs.
- Tools: `mailbox` (durable mail), `team` (chunk/seat routing, journal, oracle
  attempts, deterministic context payloads), and `taskbreak` (plan -> chunk
  seeds).
- Pipeline: 22 Gherkin features, 156 scenarios, 229 executions green; the
  features are the single source of truth (M12) with a requirement/command ->
  feature map at [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md).
- Quality: 373 persistent tests green (47 property); ruff clean; CRAP 0 functions
  above 10; DRY 0 clones. Self-hosted mutation across the 14 mutation-run
  features (every M12 feature): 377 mutants / 277 killed / 100
  documented-equivalent survivors / 0 errors.
- Design: `designer` and `task-breaker` prompts plus the
  `tools/taskbreak.py` plan -> `team_open` bridge (M8).
- Validation: M9 proved the design and execution branches converge on one
  scratch feature (51 tool calls, every seam asserted, ending drained) and fixed
  nested phase chunks being invisible to `team status --ready`; see
  [M9-VALIDATION.md](M9-VALIDATION.md).
- Pair: worker + mentor only (no senior tier, no ask or attempt caps). All eight
  agents run `opencode-go/deepseek-v4.1-flash` variant `high`.
- Prompts: all eight agent prompts written against the current tool surface
  (goal/anti-goal, XML reasoning scaffolds, contrastive examples); stale
  sealed/senior/cap wording removed.
- Reliability: **working baseline, not production-ready.** M9 (branch seams),
  M12 (specification coverage), and M10 (tool/state correctness) are done: the
  contract, recovery, and concurrency slices are executable and green, the four
  known limitations are resolved or accepted, and concurrent processes are proven
  to serialize on the real locks. The remaining gate is M6 (portability) — the
  pack is only proven self-hosting. The M6 validation program in
  [ROADMAP.md § Next](ROADMAP.md#next) gates adoption.

Open forward work is in [ROADMAP.md](ROADMAP.md).
