import { tool } from "@opencode-ai/plugin"
import path from "node:path"
import { existsSync } from "node:fs"

function findProjectRoot(start) {
  if (!start) return undefined
  let dir = path.resolve(start)
  while (true) {
    if (existsSync(path.join(dir, "swarm-forge-tin", "tools", "mailbox.py"))) return dir
    const parent = path.dirname(dir)
    if (parent === dir) return undefined
    dir = parent
  }
}

function projectRoot(context) {
  const root =
    findProjectRoot(context.directory) ??
    findProjectRoot(context.worktree) ??
    findProjectRoot(process.cwd())
  if (!root) {
    throw new Error(
      "mailbox: cannot locate swarm-forge-tin/tools/mailbox.py from context.directory, context.worktree, or process.cwd()",
    )
  }
  return root
}

async function mailbox(context, args: string[]): Promise<string> {
  const cwd = projectRoot(context)
  const script = path.join(cwd, "swarm-forge-tin", "tools", "mailbox.py")
  const proc = Bun.spawnSync(["python3", script, "--root", cwd, ...args], {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
  })
  const stdout = proc.stdout.toString().trim()
  const stderr = proc.stderr.toString().trim()
  if (proc.exitCode !== 0) {
    throw new Error([stdout, stderr].filter(Boolean).join("\n") || `mailbox exited ${proc.exitCode}`)
  }
  return [stdout, stderr].filter(Boolean).join("\n")
}

function base(context) {
  return ["--from", context.agent, "--session", context.sessionID]
}

export const send = tool({
  description:
    "Queue a durable handoff mail to one or more recipient roles. This is the only way to communicate with other roles; never write files under swarm-forge-tin/.swarmforge/mail yourself. Use type handoff (default) when work is ready for the next role; it requires a stable task name. Use type note only when a role prompt or the user explicitly directs it; a note requires a one-line message of at most 80 characters. An optional message (max 300 chars, one line) is a short pointer, never the task itself. Prints QUEUED with the mail id or DUPLICATE when the same handoff is already queued.",
  args: {
    to: tool.schema.string().describe("Comma-separated recipient roles, for example coder or specifier,coder,refactorer"),
    type: tool.schema.enum(["handoff", "note"]).optional().describe("Defaults to handoff"),
    priority: tool.schema.string().optional().describe("Two digits 00-99, lower runs first; defaults to 50"),
    task: tool.schema.string().optional().describe("Short stable task name; required for handoff and preserved when forwarding"),
    message: tool.schema.string().optional().describe("One-line pointer, max 80 chars for note, max 300 for handoff"),
  },
  async execute(args, context) {
    const argv = ["send", ...base(context), "--to", args.to]
    if (args.type) argv.push("--type", args.type)
    if (args.priority) argv.push("--priority", args.priority)
    if (args.task) argv.push("--task", args.task)
    if (args.message) argv.push("--message", args.message)
    return mailbox(context, argv)
  },
})

export const pull = tool({
  description:
    "Claim or resume your current mail. Run this when dispatched with MAIL_WAITING, and after mail_done prints MAIL_WAITING. Prints TASK with PAYLOAD (or BATCH with BATCH_ITEM payloads), or NO_TASK when the inbox is empty. One in-process item per role, owned by the session that claimed it: if you already hold one, pull resumes it; if another session holds it, pull is refused and you must not work on it. Re-running pull is safe after an interrupted call. Never read or move files under swarm-forge-tin/.swarmforge/mail yourself.",
  args: {
    mode: tool.schema.enum(["task", "batch"]).optional().describe("Use batch to claim all queued mail of the top priority as one unit; defaults to task"),
    takeover: tool.schema.boolean().optional().describe("Take ownership from a session the operator has stopped; never use without explicit operator direction"),
  },
  async execute(args, context) {
    const argv = ["pull", "--as", context.agent, "--session", context.sessionID]
    if (args.mode) argv.push("--mode", args.mode)
    if (args.takeover) argv.push("--takeover")
    return mailbox(context, argv)
  },
})

export const done = tool({
  description:
    "Complete your current in-process mail. Run this after the work is finished and any forward mail has been sent. Refused if another session owns the item. Prints COMPLETED, then MAIL_WAITING when more mail is queued (call mail_pull again) or NO_TASK when the inbox is empty. Do not run this before the task is complete; queue state is owned by the tool.",
  args: {
    id: tool.schema.string().optional().describe("Complete only this mail id; defaults to all in-process mail"),
    result: tool.schema.string().optional().describe("Optional short completion note stored in the audit record"),
  },
  async execute(args, context) {
    const argv = ["done", "--as", context.agent, "--session", context.sessionID]
    if (args.id) argv.push("--id", args.id)
    if (args.result) argv.push("--result", args.result)
    return mailbox(context, argv)
  },
})

export const status = tool({
  description:
    "Read-only mailbox summary: queued, in-process, and completed counts per role. Use this as the dispatcher to decide which role to wake with MAIL_WAITING.",
  args: {
    role: tool.schema.string().optional().describe("Limit the report to one role; defaults to all roles"),
  },
  async execute(args, context) {
    const argv = ["status", "--session", context.sessionID]
    if (args.role) argv.push("--role", args.role)
    return mailbox(context, argv)
  },
})
