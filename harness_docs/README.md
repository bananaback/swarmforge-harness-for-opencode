# Harness Docs

Index and status snapshot. Read this first in a new session.

**Updated:** 2026-09-14 · **Working tree:** uncommitted (wiring + self-hosting changes)

## Where We Are

- The harness now points at itself: `swarm-forge-tin/harness.json` sets
  `workspace_root = ".."` and `source_roots = ["tools"]`.
- The wiring seam is implemented and tool-native: `harness.json` + `tools/wiring.py` +
  `.opencode/lib/wiring.ts` + `tools/harness` CLI (`config` / `status` / `clean`).
- Test areas are split: `harness_tests/persistent/` (self-tests),
  `project_tests/persistent/` (src-project, pack-side), `hot_tests/` (shared generated).
- The acceptance pipeline is restored and self-hosted: `harness_tests/persistent/acceptance/`
  parses `harness_wiring.feature` (6 scenarios) into `hot_tests/acceptance/` and runs green.
- `AGENTS.md` and all 7 role prompts resolve paths from the wiring instead of hardcoding.

**Self-hosted verification:** 25 persistent tests pass; 6/6 acceptance scenarios pass;
ruff clean; CRAP 0 functions above 10; DRY 0 clones; `harness clean hot` leaves persistent
tests intact.

## Doc Index

| File | Purpose | Status |
|---|---|---|
| `HARNESS_WIRING.md` | Wiring design, config schema, resolution order, deliverables, next | current |
| `PROJECT_STRUCTURE.md` | Full tree, config, tooling quick reference, verification status | current |
| `TEST_PERSISTENCE_POLICY.md` | Which test artifacts persist vs regenerate | current |
| `TEAM_TOOL_DESIGN.md` | Team chunk/seat tool design (mail/team routing) | current (paths via wiring) |
| `WORKFLOW_ROUTING.md` | Model tiers and role→model routing | current |
| `TEAM_JOURNAL_EXAMPLE.md` | Sample worker journal (attempts, ask, brief) | reference |
| `prompting-guide.md` | General prompting notes | reference (not part of the pack) |
| `CONVERSION.md` | Conversion history; do not read per AGENTS.md | historical |

## Done

1. Cleanup: removed the old `src/` experiment, its tests, `tmp/`, root HTML reports.
2. Docs moved to `harness_docs/`; test structure organized into persistent vs hot.
3. Wiring implemented: config, Python + TS resolvers, per-tool artifact/state routing,
   `harness` CLI with guarded `clean`.
4. Prompts updated to the wiring model.
5. Self-hosting run: Gherkin feature + acceptance pipeline + unit/property/tool tests;
   process found and fixed 5 issues (`dry4py` multi-root crash, generator path depth,
   stale hot default, `run_cli` namespace bug, acceptance fixture CLI path).

## Next

- Wire `gherkin-mutator` runs to `hot_tests/mutation/` and add a runner/report.
- `team open --pack` could emit a generated `wiring.md` with resolved paths in the pack.
- Add automated coverage for the TS resolver (`wiring.ts`); today it has `node --check`
  plus a manual smoke only.
- Fill `project_tests/` when a production project is wired in
  (`SWARM_CONFIG=/path/to/project/harness.json` or by editing `workspace_root`).
- Commit the current work when directed; nothing is committed yet.

## Switching Projects

- Same pack, other project: `SWARM_CONFIG=/path/to/project/harness.json`, or edit
  `workspace_root` in `swarm-forge-tin/harness.json`.
- Before switching: `swarm-forge-tin/tools/harness clean all` (or `hot`, `state`,
  `artifacts` individually). `clean state` refuses while mail/team items are in process
  unless `--force`.
