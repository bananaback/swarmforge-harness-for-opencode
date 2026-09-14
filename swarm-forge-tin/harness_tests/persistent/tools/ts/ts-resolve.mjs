// Node resolve hook for the opencode TS bridges: the pack's `.ts` modules use
// TypeScript-style extensionless relative imports (`./wiring`), which Bun
// resolves but plain Node does not. This hook retries a failed relative
// resolution with a `.ts` suffix so the real modules load unmodified under
// `node --import ts-resolve.mjs`.

import { existsSync } from "node:fs"
import { registerHooks } from "node:module"
import { fileURLToPath } from "node:url"

registerHooks({
  resolve(specifier, context, nextResolve) {
    try {
      return nextResolve(specifier, context)
    } catch (error) {
      const relative = specifier.startsWith("./") || specifier.startsWith("../")
      if (relative && context.parentURL) {
        const candidate = specifier + ".ts"
        try {
          if (existsSync(fileURLToPath(new URL(candidate, context.parentURL)))) {
            return nextResolve(candidate, context)
          }
        } catch {
          // fall through to the original resolution error
        }
      }
      throw error
    }
  },
})
