// Wiring resolver for the opencode bridges: locates the harness pack and
// workspace from harness.json, SWARM_* environment overrides, or the legacy
// marker. Mirrors swarm-forge-tin/tools/wiring.py.

import path from "node:path"
import { existsSync, readFileSync } from "node:fs"
import { homedir } from "node:os"
import { fileURLToPath } from "node:url"

export type PersistentTest = {
  root: string
  pythonpath: string[]
  kind: string
}

export type Wiring = {
  packRoot: string
  workspaceRoot: string
  stateRoot: string
  artifactsRoot: string
  hotTests: string
  persistentTests: PersistentTest[]
  sourceRoots: string[]
  configPath?: string
}

const CONFIG_NAME = "harness.json"

function expand(value: string, base: string): string {
  let raw = value
  if (raw === "~") raw = homedir()
  else if (raw.startsWith("~/")) raw = path.join(homedir(), raw.slice(2))
  return path.isAbsolute(raw) ? path.resolve(raw) : path.resolve(base, raw)
}

export function findConfig(start?: string): string | undefined {
  const override = process.env.SWARM_CONFIG
  if (override) return path.resolve(override)
  // With no start, walk up from the working directory like the Python
  // resolver, instead of skipping straight to the pack and global fallbacks.
  let dir = start ? path.resolve(start) : process.cwd()
  while (true) {
    const direct = path.join(dir, CONFIG_NAME)
    if (existsSync(direct)) return direct
    const nested = path.join(dir, "swarm-forge-tin", CONFIG_NAME)
    if (existsSync(nested)) return nested
    const parent = path.dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  const packOverride = process.env.SWARM_PACK
  if (packOverride) {
    const candidate = path.join(expand(packOverride, process.cwd()), CONFIG_NAME)
    if (existsSync(candidate)) return candidate
  }
  // Fall back to the pack that provides this resolver, mirroring
  // wiring.py's PACK_ROOT / harness.json.
  const packRoot = findPack(path.dirname(fileURLToPath(import.meta.url)))
  if (packRoot) {
    const candidate = path.join(packRoot, CONFIG_NAME)
    if (existsSync(candidate)) return candidate
  }
  const globalConfig = path.join(homedir(), ".config", "swarm-forge", CONFIG_NAME)
  if (existsSync(globalConfig)) return globalConfig
  return undefined
}

export function findPack(start?: string): string | undefined {
  if (!start) return undefined
  let dir = path.resolve(start)
  while (true) {
    if (existsSync(path.join(dir, "tools", "wiring.py"))) return dir
    const nested = path.join(dir, "swarm-forge-tin")
    if (existsSync(path.join(nested, "tools", "wiring.py"))) return nested
    const parent = path.dirname(dir)
    if (parent === dir) return undefined
    dir = parent
  }
}

export function loadWiring(start?: string): Wiring {
  const base = path.resolve(start ?? process.cwd())
  const configPath = findConfig(base)
  const data = configPath
    ? (JSON.parse(readFileSync(configPath, "utf8")) as Record<string, unknown>)
    : {}
  const configDir = configPath ? path.dirname(configPath) : base
  const packRoot =
    configPath && existsSync(path.join(configDir, "tools", "wiring.py"))
      ? configDir
      : findPack(base) ??
        (process.env.SWARM_PACK ? expand(process.env.SWARM_PACK, process.cwd()) : undefined)
  if (!packRoot) throw new Error(`cannot locate the harness pack from ${base}`)
  const workspaceRoot = process.env.SWARM_WORKSPACE
    ? expand(process.env.SWARM_WORKSPACE, process.cwd())
    : typeof data.workspace_root === "string"
      ? expand(data.workspace_root, configDir)
      : path.dirname(packRoot)
  const stateRoot = process.env.SWARM_STATE_ROOT
    ? expand(process.env.SWARM_STATE_ROOT, process.cwd())
    : typeof data.state_root === "string"
      ? expand(data.state_root, configDir)
      : path.join(workspaceRoot, "swarm-forge-tin", ".swarmforge")
  const artifactsRoot =
    typeof data.artifacts_root === "string"
      ? expand(data.artifacts_root, configDir)
      : path.join(packRoot, "dump")
  const hotTests = process.env.SWARM_HOT
    ? expand(process.env.SWARM_HOT, process.cwd())
    : typeof data.hot_tests === "string"
      ? expand(data.hot_tests, configDir)
      : path.join(packRoot, "harness_tests", "hot")
  const persistentTests: PersistentTest[] = Array.isArray(data.persistent_tests)
    ? (data.persistent_tests as Array<{ root: string; pythonpath?: string[]; kind?: string }>).map(
        (entry) => {
          const root = expand(entry.root, configDir)
          return {
            root,
            pythonpath: (entry.pythonpath ?? []).map((item) => expand(item, root)),
            kind: entry.kind ?? "test",
          }
        },
      )
    : []
  const sourceRoots = Array.isArray(data.source_roots)
    ? (data.source_roots as string[]).map((item) => expand(item, configDir))
    : [expand("src", configDir)]
  return {
    packRoot,
    workspaceRoot,
    stateRoot,
    artifactsRoot,
    hotTests,
    persistentTests,
    sourceRoots,
    configPath,
  }
}
