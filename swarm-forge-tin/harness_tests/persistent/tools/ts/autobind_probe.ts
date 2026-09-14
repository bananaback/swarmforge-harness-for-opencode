// CLI probe for the team auto-bind core: binds a session to the pending seat
// for an agent, exactly as the `chat.message` plugin hook does on a
// `TEAM_WAITING` wake, and prints the result as one JSON line.
//
// usage:
//   node --import ./ts-resolve.mjs autobind_probe.ts <directory> <session> <agent>

import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const LIB = process.env.SWARM_TS_LIB ?? path.resolve(here, "../../../../../.opencode/lib")
const { autoBindPendingSeat } = await import(pathToFileURL(path.join(LIB, "team-autobind.ts")).href)

const [directory, session, agent] = process.argv.slice(2)
const result = autoBindPendingSeat(directory, session, agent)
process.stdout.write(JSON.stringify(result) + "\n")
