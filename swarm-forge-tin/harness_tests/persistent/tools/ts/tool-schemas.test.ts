// Guards the opencode custom-tool arg schemas.
//
// opencode converts every custom tool's `args` to JSON Schema when it builds
// the tool registry at startup. `tool.schema` is zod v4, where `record` takes
// `(keyType, valueType)`; a v3-only `z.record(z.any())` leaves the value type
// undefined and makes that conversion throw, so opencode fails to start before
// any session exists. This suite loads the real `.opencode/tools/*.ts` modules
// and runs opencode's own conversion so the mistake is caught here instead.
//
// Run directly:
//   node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON \
//     --import ./ts-resolve.mjs --test ./tool-schemas.test.ts

import assert from "node:assert/strict"
import { readdirSync } from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const LIB = process.env.SWARM_TS_LIB ?? path.resolve(here, "../../../../../.opencode/lib")
const WORKSPACE = path.resolve(LIB, "../..")
const TOOLS_DIR = path.join(WORKSPACE, ".opencode", "tools")
const PLUGIN = path.join(WORKSPACE, ".opencode", "node_modules", "@opencode-ai", "plugin", "dist", "index.js")

const { tool } = await import(pathToFileURL(PLUGIN).href)
const z = tool.schema

// Mirror of opencode packages/opencode/src/tool/registry.ts (`zodMetadataRegistry`
// and `zodJsonSchema`), which is the path that runs at startup.
function isZodType(value) {
  return typeof value === "object" && value !== null && "_zod" in value
}

function isJsonSchemaObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function zodMetadataRegistry(schema) {
  const registry = z.registry()
  const seen = new WeakSet()
  const collect = (value) => {
    if (typeof value !== "object" || value === null) return
    if (seen.has(value)) return
    seen.add(value)
    if (isZodType(value)) {
      const metadata = typeof value.meta === "function" ? value.meta() : undefined
      const description = typeof value.description === "string" ? value.description : undefined
      const merged = {
        ...(metadata && typeof metadata === "object" ? metadata : {}),
        ...(description ? { description } : {}),
      }
      if (Object.keys(merged).length) registry.add(value, merged)
      collect(value._zod.def)
      return
    }
    for (const item of Object.values(value)) collect(item)
  }
  collect(schema)
  return registry
}

function zodJsonSchema(schema) {
  const result = z.toJSONSchema(schema, { io: "input", metadata: zodMetadataRegistry(schema) })
  if (!isJsonSchemaObject(result)) throw new Error("plugin tool Zod schema produced a non-object JSON Schema")
  return result
}

const toolFiles = readdirSync(TOOLS_DIR).filter((file) => file.endsWith(".ts"))

test("every custom tool arg schema converts to JSON Schema like opencode does", async () => {
  const checked = []
  for (const file of toolFiles) {
    const module = await import(pathToFileURL(path.join(TOOLS_DIR, file)).href)
    for (const [exportName, definition] of Object.entries(module)) {
      const args = definition && definition.args
      if (!args) continue
      for (const [argName, schema] of Object.entries(args)) {
        zodJsonSchema(schema)
        checked.push(`${file}:${exportName}.${argName}`)
      }
    }
  }
  assert.ok(checked.length > 0, "expected at least one tool arg schema")
})

test("the journal entry accepts an object and a JSON string", async () => {
  const team = await import(pathToFileURL(path.join(TOOLS_DIR, "team.ts")).href)
  const entry = team.journal.args.entry
  assert.ok(entry.safeParse({ cleanup: "x", files: ["a"] }).success, "object entry must validate")
  assert.ok(entry.safeParse('{"cleanup":"x"}').success, "JSON string entry must validate")
  assert.ok(entry.safeParse("@/tmp/entry.json").success, "@path entry must validate")
})
