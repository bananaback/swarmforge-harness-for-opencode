#!/usr/bin/env python3
"""taskbreak -- open one team chunk per task-breaker plan entry.

The task-breaker agent decomposes a feature and its design into conflict-free
work chunks, each with a disjoint file allowlist, a done definition, and its own
oracle. This tool is the bridge that consumes that plan: it stages each chunk's
brief and design text, then opens one team task per entry with the same fields
``team open`` accepts. No hand translation.
"""

import argparse
import contextlib
import io
import json
import os
import re
from pathlib import Path

import team
import wiring
from durable_store import run_cli

PLAN_VERSION = 1
CHUNK_ROLES = ("coder", "refactorer", "architect")
ORACLE_HEADER = "ORACLE"

OPEN_FIELDS = (
    ("--definition", "definition"),
    ("--task-text", "task_text"),
    ("--interface", "interface"),
    ("--files", "files"),
    ("--goal", "goal"),
    ("--rules", "rules"),
)


class TaskBreakError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


# --- plan parsing -----------------------------------------------------------


def slug(value):
    """Return a filesystem-safe slug for ``value``."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-.")
    return cleaned or "chunk"


def load_plan(path):
    try:
        text = Path(path).read_text()
    except OSError as error:
        raise TaskBreakError([f"cannot read plan: {error}"])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise TaskBreakError([f"plan is not valid JSON: {error}"])
    if not isinstance(data, dict):
        raise TaskBreakError(["plan must be a JSON object"])
    return data


def resolve_path(value, base):
    """Resolve ``value`` against ``base`` unless it is already absolute."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(base) / path


def resolve_feature(plan, chunk, root):
    """Return the .feature path for a chunk, or None."""
    value = chunk.get("feature") or plan.get("feature")
    return resolve_path(value, root) if value else None


def missing(root, value):
    """True when ``value`` names a file that is not present under ``root``."""
    return bool(value) and not resolve_path(value, root).is_file()


def chunk_input_problems(chunk, index, root):
    """Return problems for one chunk's missing referenced input files."""
    if not isinstance(chunk, dict):
        return []
    return [
        f"chunk {index} {field} not found: {chunk.get(field)}"
        for field in ("brief", "design", "feature")
        if missing(root, chunk.get(field))
    ]


def input_problems(plan, root):
    """Return problems for any referenced brief/design/feature file missing."""
    problems = []
    if missing(root, plan.get("feature")):
        problems.append(f"feature not found: {plan['feature']}")
    for index, chunk in enumerate(plan.get("chunks", []), start=1):
        problems.extend(chunk_input_problems(chunk, index, root))
    return problems


def chunk_problem(chunk, index, seen):
    """Return the validation problems for one plan chunk."""
    where = f"chunk {index}"
    if not isinstance(chunk, dict):
        return [f"{where} must be an object"]
    problems = []
    task = chunk.get("task")
    if not task:
        problems.append(f"{where} requires a `task` name")
    elif team.task_problem(task):
        problems.append(f"{where}: {team.task_problem(task)}")
    elif task in seen:
        problems.append(f"{where} task `{task}` is duplicated")
    else:
        seen.add(task)
    if chunk.get("role") not in CHUNK_ROLES:
        problems.append(f"{where} role must be one of: {', '.join(CHUNK_ROLES)}")
    if not chunk.get("brief_text") and not chunk.get("brief"):
        problems.append(f"{where} requires `brief_text` or `brief`")
    return problems


def plan_problems(plan):
    """Return every validation problem for the plan, in order."""
    if plan.get("version", PLAN_VERSION) != PLAN_VERSION:
        return [f"plan version must be {PLAN_VERSION}"]
    chunks = plan.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return ["plan requires a non-empty `chunks` list"]
    problems = []
    seen = set()
    for index, chunk in enumerate(chunks, start=1):
        problems.extend(chunk_problem(chunk, index, seen))
    return problems


# --- staging ----------------------------------------------------------------


def staging_dir(root, plan_path):
    """Return the directory that holds the staged chunk briefs and designs."""
    resolved = wiring.load(start=root)
    return resolved.artifacts_root / "taskbreak" / slug(Path(plan_path).stem)


def chunk_text(chunk, text_field, path_field, root):
    """Return the chunk's text from the inline field, then the referenced file."""
    text = chunk.get(text_field)
    if text:
        return text
    referenced = chunk.get(path_field)
    if not referenced:
        return None
    return resolve_path(referenced, root).read_text()


def with_oracle(text, oracle):
    """Append the ORACLE section to ``text`` when one is not already present."""
    if not oracle:
        return text
    if any(line.strip().upper() == ORACLE_HEADER for line in text.splitlines()):
        return text
    return f"{text.rstrip()}\n\n{ORACLE_HEADER}\n{oracle}\n"


def stage(staging, index, task, suffix, text):
    """Write one staged chunk input file and return its path."""
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"{index:02d}-{slug(task)}.{suffix}.md"
    path.write_text(text)
    return path


def staged_brief(chunk, root, staging, index):
    text = chunk_text(chunk, "brief_text", "brief", root)
    return stage(staging, index, chunk["task"], "brief", with_oracle(text, chunk.get("oracle")))


def staged_design(chunk, root, staging, index):
    text = chunk_text(chunk, "design_text", "design", root)
    if text is None:
        return None
    return stage(staging, index, chunk["task"], "design", text)


# --- opening ----------------------------------------------------------------


def build_open_argv(root, state, chunk, brief, design, feature):
    """Build the ``team open`` argv for one staged chunk."""
    argv = ["--root", root]
    if state:
        argv += ["--state-root", state]
    argv += ["open", chunk["task"], "--role", chunk["role"], "--brief", str(brief)]
    if design:
        argv += ["--design", str(design)]
    if feature:
        argv += ["--feature", str(feature)]
    for flag, field in OPEN_FIELDS:
        value = chunk.get(field)
        if value:
            argv += [flag, str(value)]
    return argv


def run_team_open(argv):
    """Run ``team open`` in-process, keeping its human output off our stdout."""
    with contextlib.redirect_stdout(io.StringIO()):
        return team.main(argv)


def open_chunk(root, state, plan, chunk, staging, index, dry_run):
    """Stage one chunk and open its team task; return the task name."""
    brief = staged_brief(chunk, root, staging, index)
    design = staged_design(chunk, root, staging, index)
    feature = resolve_feature(plan, chunk, root)
    argv = build_open_argv(root, state, chunk, brief, design, feature)
    if not dry_run and run_team_open(argv) != 0:
        raise TaskBreakError([f"team open failed for chunk `{chunk['task']}`"])
    return chunk["task"]


def emit(args, opened):
    if args.json:
        print(json.dumps({"command": "taskbreak", "opened": opened}, indent=2, sort_keys=True))
        return
    for task in opened:
        print(f"OPENED: {task}")
    if args.dry_run:
        print("DRY RUN: no chunks opened")


def cmd_plan(args):
    """Parse the plan, stage its chunks, and open each one."""
    plan_path = Path(args.plan).expanduser().resolve()
    root = str(Path(args.root).resolve())
    plan = load_plan(plan_path)
    problems = plan_problems(plan) or input_problems(plan, root)
    if problems:
        raise TaskBreakError(problems)
    staging = staging_dir(root, plan_path)
    opened = [
        open_chunk(root, args.state_root, plan, chunk, staging, index, args.dry_run)
        for index, chunk in enumerate(plan["chunks"], start=1)
    ]
    emit(args, opened)


def build_parser():
    parser = argparse.ArgumentParser(prog="taskbreak")
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--state-root")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_plan)
    return parser


def main(argv=None):
    return run_cli(build_parser, TaskBreakError, "TASKBREAK", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
