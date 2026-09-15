// Automated coverage for the opencode bridges: the TS wiring resolver
// (`.opencode/lib/wiring.ts`) and the seat auto-bind core
// (`.opencode/lib/team-autobind.ts`). These modules run under opencode's Bun
// runtime; this suite loads the same sources under Node (native type stripping
// plus the `ts-resolve.mjs` hook) so their behavior is pinned without a full
// opencode spawn.
//
// Run directly:
//   node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON \
//     --import ./ts-resolve.mjs --test ./wiring.test.ts
// or through the Python wrapper (test_ts_wiring.py) in the persistent suite.

import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"
import test, { after } from "node:test"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const LIB = process.env.SWARM_TS_LIB ?? path.resolve(here, "../../../../../.opencode/lib")
const WORKSPACE = path.resolve(LIB, "../..")
const REAL_PACK = path.join(WORKSPACE, "swarm-forge-tin")

const { findConfig, loadWiring } = await import(pathToFileURL(path.join(LIB, "wiring.ts")).href)
const { parseReady, seatForAgent, autoBindPendingSeat, messageText } = await import(
  pathToFileURL(path.join(LIB, "team-autobind.ts")).href
)

const ENV_KEYS = ["SWARM_CONFIG", "SWARM_PACK", "SWARM_WORKSPACE", "SWARM_STATE_ROOT", "SWARM_HOT"]
const tempDirs = []

after(() => {
  for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true })
})

function tempDir() {
  const dir = mkdtempSync(path.join(tmpdir(), "swarm-ts-"))
  tempDirs.push(dir)
  return dir
}

function withEnv(values, fn) {
  const saved = {}
  for (const key of ENV_KEYS) saved[key] = process.env[key]
  for (const key of ENV_KEYS) delete process.env[key]
  Object.assign(process.env, values)
  try {
    return fn()
  } finally {
    for (const key of ENV_KEYS) {
      if (saved[key] === undefined) delete process.env[key]
      else process.env[key] = saved[key]
    }
  }
}

// A throwaway pack whose config directory carries `tools/wiring.py`, so the
// resolver treats that directory as the pack root (matching a real pack).
function makePack(fields) {
  const pack = tempDir()
  mkdirSync(path.join(pack, "tools"), { recursive: true })
  writeFileSync(path.join(pack, "tools", "wiring.py"), "")
  const config = path.join(pack, "harness.json")
  writeFileSync(config, JSON.stringify({ version: 1, ...fields }))
  return { pack, config }
}

test("findConfig prefers SWARM_CONFIG and resolves it absolutely", () => {
  const dir = tempDir()
  const config = path.join(dir, "harness.json")
  writeFileSync(config, "{}")
  withEnv({ SWARM_CONFIG: config }, () => {
    assert.equal(findConfig(path.join(dir, "nested")), path.resolve(config))
  })
})

test("findConfig walks upward to the nearest harness.json", () => {
  const root = tempDir()
  writeFileSync(path.join(root, "harness.json"), "{}")
  const nested = path.join(root, "a", "b")
  mkdirSync(nested, { recursive: true })
  withEnv({}, () => {
    assert.equal(findConfig(nested), path.join(root, "harness.json"))
  })
})

test("findConfig finds the config nested under swarm-forge-tin", () => {
  const root = tempDir()
  const pack = path.join(root, "swarm-forge-tin")
  mkdirSync(pack, { recursive: true })
  writeFileSync(path.join(pack, "harness.json"), "{}")
  withEnv({}, () => {
    assert.equal(findConfig(root), path.join(pack, "harness.json"))
  })
})

test("findConfig falls back to SWARM_PACK after walk-up fails", () => {
  const root = tempDir()
  writeFileSync(path.join(root, "harness.json"), "{}")
  const neutral = tempDir()
  const previous = process.cwd()
  process.chdir(neutral)
  try {
    withEnv({ SWARM_PACK: root }, () => {
      assert.equal(findConfig(), path.join(root, "harness.json"))
    })
  } finally {
    process.chdir(previous)
  }
})

test("findConfig with no start walks up from the working directory", () => {
  const root = tempDir()
  writeFileSync(path.join(root, "harness.json"), "{}")
  const nested = path.join(root, "a", "b")
  mkdirSync(nested, { recursive: true })
  const previous = process.cwd()
  process.chdir(nested)
  try {
    withEnv({}, () => {
      assert.equal(findConfig(), path.join(root, "harness.json"))
    })
  } finally {
    process.chdir(previous)
  }
})

test("findConfig with no start falls back to the resolver's pack config", () => {
  const dir = tempDir()
  const previous = process.cwd()
  process.chdir(dir)
  try {
    withEnv({}, () => {
      assert.equal(findConfig(), path.join(REAL_PACK, "harness.json"))
    })
  } finally {
    process.chdir(previous)
  }
})

test("findConfig falls back to the resolver's pack when a start has no config", () => {
  const root = tempDir()
  withEnv({}, () => {
    assert.equal(findConfig(root), path.join(REAL_PACK, "harness.json"))
  })
})

test("loadWiring expands configured roots relative to the config", () => {
  const { pack, config } = makePack({
    workspace_root: "..",
    state_root: ".swarmforge",
    artifacts_root: "artifacts",
    hot_tests: "hot",
    persistent_tests: [{ root: "tests", pythonpath: [".", "src"], kind: "project" }],
    source_roots: ["src", "lib"],
  })
  withEnv({ SWARM_CONFIG: config }, () => {
    const wiring = loadWiring(pack)
    assert.equal(wiring.packRoot, pack)
    assert.equal(wiring.workspaceRoot, path.dirname(pack))
    assert.equal(wiring.stateRoot, path.join(pack, ".swarmforge"))
    assert.equal(wiring.artifactsRoot, path.join(pack, "artifacts"))
    assert.equal(wiring.hotTests, path.join(pack, "hot"))
    assert.deepEqual(wiring.persistentTests, [
      {
        root: path.join(pack, "tests"),
        pythonpath: [path.join(pack, "tests"), path.join(pack, "tests", "src")],
        kind: "project",
      },
    ])
    assert.deepEqual(wiring.sourceRoots, [path.join(pack, "src"), path.join(pack, "lib")])
    assert.equal(wiring.configPath, config)
  })
})

test("loadWiring applies defaults for absent fields", () => {
  const { pack, config } = makePack({ workspace_root: "." })
  withEnv({ SWARM_CONFIG: config }, () => {
    const wiring = loadWiring(pack)
    assert.equal(wiring.workspaceRoot, pack)
    assert.equal(wiring.stateRoot, path.join(pack, "swarm-forge-tin", ".swarmforge"))
    assert.equal(wiring.artifactsRoot, path.join(pack, "dump"))
    assert.equal(wiring.hotTests, path.join(pack, "harness_tests", "hot"))
    assert.deepEqual(wiring.persistentTests, [])
    assert.deepEqual(wiring.sourceRoots, [path.join(pack, "src")])
  })
})

test("loadWiring honors SWARM_* environment overrides", () => {
  const { pack, config } = makePack({ workspace_root: "." })
  const workspace = tempDir()
  const state = tempDir()
  const hot = tempDir()
  withEnv(
    {
      SWARM_CONFIG: config,
      SWARM_WORKSPACE: workspace,
      SWARM_STATE_ROOT: state,
      SWARM_HOT: hot,
    },
    () => {
      const wiring = loadWiring(pack)
      assert.equal(wiring.workspaceRoot, workspace)
      assert.equal(wiring.stateRoot, state)
      assert.equal(wiring.hotTests, hot)
    },
  )
})

test("loadWiring falls back to the resolver's pack from a config-less directory", () => {
  const dir = tempDir()
  withEnv({}, () => {
    const wiring = loadWiring(dir)
    assert.equal(wiring.packRoot, REAL_PACK)
    assert.equal(wiring.configPath, path.join(REAL_PACK, "harness.json"))
  })
})

test("seatForAgent maps pack roles to team seats", () => {
  assert.equal(seatForAgent("coder"), "worker")
  assert.equal(seatForAgent("refactorer"), "worker")
  assert.equal(seatForAgent("architect"), "worker")
  assert.equal(seatForAgent("mentor"), "mentor")
  assert.equal(seatForAgent("senior"), null)
  assert.equal(seatForAgent("orchestrator"), null)
  assert.equal(seatForAgent(undefined), null)
})

test("parseReady extracts READY rows and ignores noise", () => {
  const output = [
    "READY: c1 worker SPAWN_PENDING",
    "garbage",
    "READY: c1 mentor queued",
    "READY: c2 mentor SPAWN_PENDING",
    "READY: c3 worker bogus",
    "",
  ].join("\n")
  assert.deepEqual(parseReady(output), [
    { chunk: "c1", seat: "worker", state: "SPAWN_PENDING" },
    { chunk: "c1", seat: "mentor", state: "queued" },
    { chunk: "c2", seat: "mentor", state: "SPAWN_PENDING" },
  ])
})

test("parseReady returns no rows for READY: none", () => {
  assert.deepEqual(parseReady("READY: none\n"), [])
})

test("messageText joins the parts of a wake message", () => {
  assert.equal(messageText({ parts: [{ text: "TEAM_WAITING:" }, { text: "run team_pull" }] }), "TEAM_WAITING: run team_pull")
  assert.equal(messageText(undefined), "")
})

test("autoBindPendingSeat skips an agent with no seat mapping", () => {
  const result = autoBindPendingSeat(process.cwd(), "s-orchestrator", "orchestrator")
  assert.equal(result.bound, false)
  assert.match(result.reason, /no seat mapping/)
})

test("autoBindPendingSeat reports no pending seat when state is empty", () => {
  const root = tempDir()
  const config = path.join(root, "harness.json")
  writeFileSync(config, JSON.stringify({ version: 1, workspace_root: ".", state_root: "state" }))
  withEnv({ SWARM_CONFIG: config, SWARM_PACK: REAL_PACK }, () => {
    const result = autoBindPendingSeat(root, "s-worker", "coder")
    assert.equal(result.bound, false)
    assert.match(result.reason, /no SPAWN_PENDING worker seat/)
  })
})

test("the real self-hosted pack resolves from the workspace", () => {
  assert.ok(existsSync(path.join(REAL_PACK, "harness.json")))
  withEnv({}, () => {
    const wiring = loadWiring(WORKSPACE)
    assert.equal(wiring.packRoot, REAL_PACK)
    assert.equal(wiring.workspaceRoot, WORKSPACE)
  })
})
