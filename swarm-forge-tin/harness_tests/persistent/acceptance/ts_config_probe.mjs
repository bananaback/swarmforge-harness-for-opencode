// Acceptance probe: resolve the harness config with no start, mirroring the
// opencode bridge call `findConfig()` in `.opencode/lib/wiring.ts`. The step
// handler sets the working directory, so process.cwd() drives the walk-up.

import { pathToFileURL } from "node:url"

const modulePath = process.env.SWARM_TS_WIRING
if (!modulePath) {
  process.stderr.write("SWARM_TS_WIRING is not set\n")
  process.exit(2)
}
const { findConfig } = await import(pathToFileURL(modulePath).href)
process.stdout.write(`${findConfig() ?? ""}\n`)
