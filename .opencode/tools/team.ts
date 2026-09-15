import { tool } from "@opencode-ai/plugin"
import path from "node:path"
import { loadWiring } from "../lib/wiring"

function roots(context) {
  const start = context.directory ?? context.worktree ?? process.cwd()
  try {
    return loadWiring(start)
  } catch (error) {
    throw new Error(`team: cannot locate the harness pack or config from ${start}: ${error}`)
  }
}

async function team(context, args: string[]): Promise<string> {
  const resolved = roots(context)
  const script = path.join(resolved.packRoot, "tools", "team.py")
  const proc = Bun.spawnSync(["python3", script, "--root", resolved.workspaceRoot, ...args], {
    cwd: resolved.workspaceRoot,
    stdout: "pipe",
    stderr: "pipe",
  })
  const stdout = proc.stdout.toString().trim()
  const stderr = proc.stderr.toString().trim()
  if (proc.exitCode !== 0) {
    throw new Error([stdout, stderr].filter(Boolean).join("\n") || `team exited ${proc.exitCode}`)
  }
  return [stdout, stderr].filter(Boolean).join("\n")
}

function session(context) {
  return ["--session", context.sessionID]
}

export const open = tool({
  description:
    "Control (orchestrator only): open a task's dated chunk layout, copy its inputs, and seed the worker seat. State lives under <state>/tasks/<UTC-date>/<task>/<NN-role>/. Run team_bind (or rely on team-autobind) to bind each spawned session to its seat.",
  args: {
    task: tool.schema.string().describe("Task id, e.g. task_state_layout or context-engineering/refactorer"),
    role: tool.schema.string().describe("Role for the first chunk: coder, refactorer, or architect"),
    brief: tool.schema.string().optional().describe("Path to the brief file copied into input/"),
    feature: tool.schema.string().optional().describe("Path to the feature file copied into input/ (parsed IR copied too)"),
    design: tool.schema.string().optional().describe("Path to the design file copied into input/"),
  },
  async execute(args, context) {
    const argv = ["open", args.task, "--role", args.role]
    if (args.brief) argv.push("--brief", args.brief)
    if (args.feature) argv.push("--feature", args.feature)
    if (args.design) argv.push("--design", args.design)
    return team(context, argv)
  },
})

export const bind = tool({
  description:
    "Control (orchestrator only): atomically bind a spawned session to a seat of a task. Refused if the seat is already bound; pass takeover after the operator confirms the old session is stopped. Re-binding resets that seat's context cursor.",
  args: {
    task: tool.schema.string().describe("Task id"),
    seat: tool.schema.enum(["worker", "mentor"]).describe("Seat to bind"),
    session: tool.schema.string().describe("Session id returned by the spawn"),
    takeover: tool.schema.boolean().optional().describe("Replace an existing binding; operator-confirmed only"),
  },
  async execute(args, context) {
    const argv = ["bind", args.task, "--seat", args.seat, "--session", args.session]
    if (args.takeover) argv.push("--takeover")
    return team(context, argv)
  },
})

export const status = tool({
  description:
    "Read-only team status: per-task roles, bindings, cursors, and queue counts. With ready, list seats that have queued items as SPAWN_PENDING (unbound) or queued (bound) so the orchestrator knows whom to spawn or wake.",
  args: {
    ready: tool.schema.boolean().optional().describe("List only seats with queued items"),
  },
  async execute(args, context) {
    const argv = ["status"]
    if (args.ready) argv.push("--ready")
    return team(context, argv)
  },
})

export const close = tool({
  description:
    "Control (orchestrator only): close a task. With preserve, move the whole task folder to <state>/done/; without it, delete exactly that task. A preserved task and its journal stay on disk for audit.",
  args: {
    task: tool.schema.string().describe("Task id"),
    preserve: tool.schema.boolean().optional().describe("Move the task to done/ instead of deleting it"),
  },
  async execute(args, context) {
    const argv = ["close", args.task]
    if (args.preserve) argv.push("--preserve")
    return team(context, argv)
  },
})

export const pull = tool({
  description:
    "Claim or resume the in-process item for the caller's seat. The chunk and seat come from the caller's session binding, so never pass them. Prints TASK with the item payload, or NO_TASK. Re-running is safe and resumes the same item.",
  args: {
    seat: tool.schema.enum(["worker", "mentor"]).optional().describe("Optional hint, validated against the caller's binding"),
  },
  async execute(args, context) {
    const argv = ["pull", ...session(context)]
    if (args.seat) argv.push("--seat", args.seat)
    return team(context, argv)
  },
})

export const send = tool({
  description:
    "Send a message to another seat in the caller's chunk. Models name only the target seat; the chunk comes from the caller's binding. Edges are fixed: worker->mentor ask, mentor->worker brief. The pair may exchange as many asks and briefs as the problem needs; there is no cap.",
  args: {
    to: tool.schema.enum(["worker", "mentor"]).describe("Target seat"),
    kind: tool.schema.enum(["ask", "brief"]).describe("Message kind; must match the edge"),
    message: tool.schema.string().describe("The message body (may be multi-line)"),
  },
  async execute(args, context) {
    return team(context, [
      "send",
      ...session(context),
      "--to",
      args.to,
      "--kind",
      args.kind,
      "--message",
      args.message,
    ])
  },
})

export const done = tool({
  description:
    "Complete the caller's current in-process item. Refused if another session owns it. Prints COMPLETED then READY when more mail is queued for the seat, or NO_TASK.",
  args: {
    id: tool.schema.string().optional().describe("Complete only this item id; defaults to all in-process items"),
    result: tool.schema.string().optional().describe("Optional short completion note stored in the audit record"),
  },
  async execute(args, context) {
    const argv = ["done", ...session(context)]
    if (args.id) argv.push("--id", args.id)
    if (args.result) argv.push("--result", args.result)
    return team(context, argv)
  },
})

export const context = tool({
  description:
    "Deliver chunk context to the caller's seat. First call returns the sealed pack plus the full journal and sets the cursor; later calls with delta return only journal entries since the cursor. delta before a full load is refused with LOAD_REQUIRED.",
  args: {
    delta: tool.schema.boolean().optional().describe("Return only journal entries since the seat's cursor"),
  },
  async execute(args, context) {
    const argv = ["context", ...session(context)]
    if (args.delta) argv.push("--delta")
    return team(context, argv)
  },
})

function journalEntry(value: unknown): string {
  // A model may pass the entry as a JSON object; spawn args must be strings,
  // so normalize objects to JSON text here instead of coercing to
  // "[object Object]". Strings (including @path) pass through untouched.
  const text = typeof value === "string" ? value : JSON.stringify(value)
  if (typeof text !== "string") throw new Error("team: journal entry is required")
  return text
}

export const journal = tool({
  description:
    "Worker seat only: append one journal entry (readback, plan, result, or note) to the chunk journal. Pass entry as a JSON object (a JSON string or @path to a JSON file also works); optional attempt attaches facts from the numbered attempt artifact. The journal is append-only and worker-authored.",
  args: {
    kind: tool.schema.enum(["readback", "plan", "result", "note"]).describe("Journal entry kind"),
    entry: tool.schema
      .union([tool.schema.record(tool.schema.string(), tool.schema.any()), tool.schema.string()])
      .describe("JSON object with the entry fields, a JSON string, or @path to a JSON file"),
    attempt: tool.schema.number().optional().describe("Attempt number whose attempts/NN.json facts are attached"),
  },
  async execute(args, context) {
    const argv = [
      "journal",
      ...session(context),
      "--kind",
      args.kind,
      "--entry",
      journalEntry(args.entry),
    ]
    if (args.attempt !== undefined) argv.push("--attempt", String(args.attempt))
    return team(context, argv)
  },
})

export const attempt = tool({
  description:
    "Worker seat only: run the chunk's oracle command and record it as an attempt artifact (cmd, cwd, exit, duration, full output, git diff). The output is returned and the artifact is numbered; attach it to the next result journal entry with team_journal's attempt argument.",
  args: {
    command: tool.schema.string().describe("Oracle command to run, e.g. python3 -m pytest unit/test_dateparse.py -q"),
    cwd: tool.schema.string().optional().describe("Working directory, relative to the project root; defaults to the project root"),
    timeout: tool.schema.number().optional().describe("Timeout in seconds"),
  },
  async execute(args, context) {
    const argv = ["attempt", ...session(context), "--command", args.command]
    if (args.cwd) argv.push("--cwd", args.cwd)
    if (args.timeout !== undefined) argv.push("--timeout", String(args.timeout))
    return team(context, argv)
  },
})
