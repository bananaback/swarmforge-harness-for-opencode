// Team auto-bind plugin: on a TEAM_WAITING wake message, bind the freshly
// spawned session to the matching SPAWN_PENDING seat of the open chunk
// before the child's first tool call. The task tool remains the only spawn
// path; this hook only fills the bind gap at spawn time.
//
// Skips everything that is not a team wake: the orchestrator's own
// messages, explore/scout spawns, and wakes for seats that are already
// bound (those show up as `queued`, not `SPAWN_PENDING`).

import type { Plugin } from "@opencode-ai/plugin"
import { autoBindPendingSeat, messageText } from "../lib/team-autobind"

export const TeamAutobind: Plugin = async ({ client, directory }) => {
  try {
    await client.app.log({
      body: { service: "team-autobind", level: "info", message: "team-autobind loaded" },
    })
  } catch {
    // Logging must never break plugin startup.
  }
  return {
    "chat.message": async (input, output) => {
      const { sessionID, agent } = input
      if (!sessionID) return
      const text = messageText(output?.message) || (output?.parts ?? []).map((p) => p.text ?? "").join(" ")
      if (!text.includes("TEAM_WAITING")) return
      const result = autoBindPendingSeat(directory ?? process.cwd(), sessionID, agent)
      try {
        await client.app.log({
          body: {
            service: "team-autobind",
            level: result.bound ? "info" : "debug",
            message: result.bound
              ? result.reason
              : `skip ${agent ?? "(none)"} ${sessionID}: ${result.reason}`,
          },
        })
      } catch {
        // Logging must never break the dispatch.
      }
    },
  }
}