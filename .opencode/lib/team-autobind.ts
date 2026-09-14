// Team auto-bind core: binds a freshly spawned session to the pending team
// seat of the open chunk, so the child's first team_pull already resolves.
// Pure logic only — the plugin hook (`.opencode/plugins/team-autobind.ts`)
// and the probe script both call `autoBindPendingSeat`.

import path from "node:path"
import { spawnSync } from "node:child_process"
import { loadWiring } from "./wiring"

export type Seat = "worker" | "mentor"

const AGENT_TO_SEAT: Record<string, Seat> = {
  coder: "worker",
  refactorer: "worker",
  architect: "worker",
  mentor: "mentor",
}

export function seatForAgent(agent?: string): Seat | null {
  if (!agent) return null
  return AGENT_TO_SEAT[agent] ?? null
}

export function findProjectRoot(start?: string): string | undefined {
  if (!start) return undefined
  try {
    return loadWiring(start).workspaceRoot
  } catch {
    return undefined
  }
}

export type ReadyEntry = {
  chunk: string
  seat: Seat
  state: "SPAWN_PENDING" | "queued"
}

export function parseReady(output: string): ReadyEntry[] {
  const entries: ReadyEntry[] = []
  for (const line of output.split("\n")) {
    const match = line.match(/^READY: (\S+) (\S+) (SPAWN_PENDING|queued)$/)
    if (match) entries.push({ chunk: match[1], seat: match[2] as Seat, state: match[3] as ReadyEntry["state"] })
  }
  return entries
}

export function runTeam(
  root: string,
  ...args: string[]
): { code: number; stdout: string; stderr: string } {
  const resolved = loadWiring(root)
  const proc = spawnSync(
    "python3",
    [
      path.join(resolved.packRoot, "tools", "team.py"),
      "--root",
      resolved.workspaceRoot,
      ...args,
    ],
    { cwd: resolved.workspaceRoot, encoding: "utf8" },
  )
  return {
    code: proc.status ?? -1,
    stdout: proc.stdout ?? "",
    stderr: proc.stderr ?? "",
  }
}

export type AutobindResult = {
  bound: boolean
  reason: string
}

// Find the single SPAWN_PENDING seat matching the spawned agent and bind the
// session to it. Never throws; every path returns a description.
export function autoBindPendingSeat(
  directory: string,
  sessionID: string,
  agent?: string,
): AutobindResult {
  const seat = seatForAgent(agent)
  if (!seat) return { bound: false, reason: `agent ${agent ?? "(none)"} has no seat mapping` }
  const root = findProjectRoot(directory) ?? findProjectRoot(process.cwd())
  if (!root) return { bound: false, reason: "project root not found" }
  const ready = runTeam(root, "status", "--ready")
  if (ready.code !== 0) return { bound: false, reason: `status failed: ${ready.stderr.trim()}` }
  const pending = parseReady(ready.stdout).filter(
    (entry) => entry.state === "SPAWN_PENDING" && entry.seat === seat,
  )
  if (pending.length === 0) return { bound: false, reason: `no SPAWN_PENDING ${seat} seat` }
  if (pending.length > 1)
    return { bound: false, reason: `ambiguous: ${pending.length} SPAWN_PENDING ${seat} seats` }
  const target = pending[0]
  const bound = runTeam(root, "bind", target.chunk, "--seat", target.seat, "--session", sessionID)
  if (bound.code !== 0) return { bound: false, reason: `bind failed: ${bound.stderr.trim()}` }
  return { bound: true, reason: `bound ${target.chunk} ${target.seat} to ${sessionID}` }
}

export function messageText(message: unknown): string {
  if (!message) return ""
  const msg = message as { parts?: Array<{ text?: string }> }
  return (msg.parts ?? []).map((part) => part.text ?? "").join(" ")
}