#!/usr/bin/env python3
"""Team tool -- chunk routing, journal, oracle attempts, and task state layout.

Manages per-task, per-role chunk folders under ``<state>/tasks/<UTC-date>/<task>/``
with append-only journals and write-once inputs.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import wiring
from durable_store import iso_now, read_json, run_cli, write_json_atomic
from durable_store import lock as store_lock
from durable_store import next_seq as store_next_seq

SEATS = ("worker", "mentor")
ROLES = ("orchestrator", "specifier", "coder", "refactorer", "architect", "mentor")
WORKER_KINDS = ("readback", "plan", "result", "note")
ALL_KINDS = ("open", "readback", "plan", "result", "note", "attempt", "stuck", "advice", "done")
EDGES = {
    ("worker", "mentor"): "ask",
    ("mentor", "worker"): "brief",
}
TASK_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TASK_MAX = 80


class TeamError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


# --- paths -----------------------------------------------------------------


_STATE_ROOT_OVERRIDE = None


def set_state_root(value):
    global _STATE_ROOT_OVERRIDE
    _STATE_ROOT_OVERRIDE = value


def state_root(root):
    return wiring.state_root_for(root, override=_STATE_ROOT_OVERRIDE)


def artifacts_root(root):
    return wiring.load(start=root).artifacts_root


def _today_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _tasks_root(state):
    return Path(state) / "tasks"


def _done_root(state):
    return Path(state) / "done"


def _date_dir(state, date_str=None):
    return _tasks_root(state) / (date_str or _today_str())


def _done_date_dir(state, date_str=None):
    return _done_root(state) / (date_str or _today_str())


def _task_dir(state, task, date_str=None):
    return _date_dir(state, date_str) / task


def _task_json_path(state, task, date_str=None):
    return _task_dir(state, task, date_str) / "task.json"


def _chunk_dir(state, task, chunk_name, date_str=None):
    return _task_dir(state, task, date_str) / chunk_name


def _journal_path(state, task, chunk_name, date_str=None):
    return _chunk_dir(state, task, chunk_name, date_str) / "journal.jsonl"


def _input_dir(state, task, chunk_name, date_str=None):
    return _chunk_dir(state, task, chunk_name, date_str) / "input"


def _output_dir(state, task, chunk_name, date_str=None):
    return _chunk_dir(state, task, chunk_name, date_str) / "output"


def _locks_root(state):
    return Path(state) / ".locks"


def ensure_locks(state):
    _locks_root(state).mkdir(parents=True, exist_ok=True)


# --- io --------------------------------------------------------------------


@contextmanager
def lock(state, name):
    ensure_locks(state)
    digest = hashlib.sha256(name.encode()).hexdigest()[:16]
    with store_lock(_locks_root(state), digest):
        yield


# --- validation ------------------------------------------------------------


def task_problem(task):
    if not task:
        return "task must not be empty"
    if len(task) > TASK_MAX:
        return f"task must be at most {TASK_MAX} characters"
    if task.startswith("/") or task.endswith("/") or "\\" in task:
        return "task must be a relative path without empty segments"
    for segment in task.split("/"):
        if segment in (".", "..") or not TASK_SEGMENT_RE.match(segment):
            return (
                "task segments must start alphanumeric and contain only "
                "letters, digits, '.', '_', '-'"
            )
    return None


def validate_task(task):
    problem = task_problem(task)
    if problem:
        raise TeamError([problem])


def validate_seat(seat):
    if seat not in SEATS:
        raise TeamError([f"seat must be one of: {', '.join(SEATS)}"])


def validate_role(role):
    if role not in ROLES:
        raise TeamError([f"role must be one of: {', '.join(ROLES)}"])


def validate_kind(kind):
    if kind not in ALL_KINDS:
        raise TeamError([f"kind must be one of: {', '.join(ALL_KINDS)}"])


# --- task.json / journal ---------------------------------------------------


def load_task_json(state, task, date_str=None):
    path = _task_json_path(state, task, date_str)
    if not path.is_file():
        raise TeamError([f"task `{task}` does not exist"])
    try:
        return read_json(path)
    except (OSError, ValueError) as error:
        raise TeamError([f"task `{task}` json is corrupt: {error}"])


def read_journal(state, task, chunk_name, date_str=None):
    path = _journal_path(state, task, chunk_name, date_str)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def append_journal(state, task, chunk_name, entry, date_str=None):
    path = _journal_path(state, task, chunk_name, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def next_journal_seq(state, task, chunk_name, date_str=None):
    entries = read_journal(state, task, chunk_name, date_str)
    return len(entries) + 1


# --- session resolution ----------------------------------------------------


def find_task_for_session(root, session):
    """Find (task, role, chunk_name, date_str) where session is bound."""
    state = state_root(root)
    tasks_dir = _tasks_root(state)
    if not tasks_dir.is_dir():
        return None
    for task_json in sorted(tasks_dir.rglob("task.json")):
        try:
            doc = read_json(task_json)
        except (OSError, ValueError):
            continue
        for role, info in doc.get("roles", {}).items():
            if info.get("session") == session:
                chunk_name = doc.get("chunk") or doc.get("chunk_name", "")
                # extract date: find the component directly under tasks_dir
                rel = task_json.relative_to(tasks_dir)
                date_str = rel.parts[0]
                return (doc["task"], role, chunk_name, date_str)
    return None


def resolve_binding(root, session, seat_hint=None):
    if not session:
        raise TeamError(["a session id is required for this operation"])
    match = find_task_for_session(root, session)
    if not match:
        raise TeamError(
            [
                "session is not bound to any team seat; every "
                "coder/refactorer/architect dispatch runs inside a phase "
                "chunk, so an unbound call is an orchestrator binding failure",
                "STOP and report this exact error; never rationalize it away "
                "and continue",
            ]
        )
    task, role, chunk_name, date_str = match
    if seat_hint and seat_hint != role:
        raise TeamError([f"session is bound to `{role}`, not `{seat_hint}`"])
    return task, role, chunk_name, date_str


def resolve_chunk(args, seat_hint=None):
    """Resolve the caller's chunk and prepare its lock directory."""
    state = state_root(args.root)
    task, role, chunk_name, date_str = resolve_binding(args.root, args.session, seat_hint)
    ensure_locks(state)
    return state, task, role, chunk_name, date_str


# --- git helpers ------------------------------------------------------------


def git_info(root):
    """Return {"branch": ..., "commit": ...} or empty dict."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        branch = proc.stdout.strip() if proc.returncode == 0 else "unknown"
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        commit = proc.stdout.strip() if proc.returncode == 0 else "unknown"
        return {"branch": branch, "commit": commit}
    except (OSError, subprocess.TimeoutExpired):
        return {"branch": "unknown", "commit": "unknown"}


def git_diff(root):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff"],
            capture_output=True, text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


# --- output helpers ---------------------------------------------------------


def attempt_output_path(state, task, chunk_name, number, date_str=None):
    return _output_dir(state, task, chunk_name, date_str) / f"attempt-{number:02d}.txt"


def attempt_diff_path(state, task, chunk_name, number, date_str=None):
    return _output_dir(state, task, chunk_name, date_str) / f"attempt-{number:02d}.diff"


def attempt_seq_path(state, task, chunk_name, date_str=None):
    return _output_dir(state, task, chunk_name, date_str) / ".seq"


def next_attempt_seq(state, task, chunk_name, date_str=None):
    path = attempt_seq_path(state, task, chunk_name, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    return store_next_seq(path)


# --- oracle -----------------------------------------------------------------


def kill_process_group(proc):
    """Kill the oracle and every descendant it started in its session."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def run_oracle(command, cwd, timeout):
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        output = (stdout or "") + (stderr or "")
        return proc.returncode, output, False, time.monotonic() - started
    except subprocess.TimeoutExpired:
        kill_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        output = (stdout or "") + (stderr or "")
        return 124, output, True, time.monotonic() - started


# --- entry helpers ----------------------------------------------------------


def read_entry_source(raw):
    if not raw.startswith("@"):
        return raw
    try:
        return Path(raw[1:]).read_text()
    except OSError as error:
        raise TeamError([f"cannot read entry file: {error}"])


def parse_entry(raw):
    if raw is None:
        raise TeamError(["--entry is required"])
    raw = read_entry_source(raw)
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TeamError([f"--entry must be valid JSON: {error}"])
    if not isinstance(entry, dict):
        raise TeamError(["--entry must be a JSON object"])
    return entry


# --- commands --------------------------------------------------------------


def emit(args, human, data):
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(human)


def _copy_one(src, dest):
    """Copy ``src`` into ``dest`` verbatim; return the copied name or None."""
    if not src.is_file():
        return None
    dest.mkdir(parents=True, exist_ok=True)
    (dest / src.name).write_bytes(src.read_bytes())
    return src.name


def copy_chunk_inputs(root, args, input_dir):
    """Copy the given brief/feature/design and the parsed feature IR.

    Returns the copied file names in copy order. The feature IR is read from
    the configured artifacts root, where the parse step wrote it.
    """
    inputs = []
    for src_path in (args.brief, args.feature, args.design):
        if not src_path:
            continue
        src = Path(src_path)
        name = _copy_one(src, input_dir)
        if not name:
            continue
        inputs.append(name)
        if src_path == args.feature:
            ir_name = _copy_one(artifacts_root(root) / f"{src.stem}.json", input_dir)
            if ir_name:
                inputs.append(ir_name)
    return inputs


def create_chunk_dirs(state, task, chunk_name, date_str):
    """Create the chunk folder with its write-once input and output areas."""
    _chunk_dir(state, task, chunk_name, date_str).mkdir(parents=True, exist_ok=True)
    _input_dir(state, task, chunk_name, date_str).mkdir(exist_ok=True)
    _output_dir(state, task, chunk_name, date_str).mkdir(exist_ok=True)


def mentor_fields(args, brief_text):
    """Resolve the mentor chunk-state fields from flags, then the brief."""
    fields = {}
    for name in ("goal", "rules", "ask", "failure"):
        value = getattr(args, name)
        if not value:
            value = extract_section(brief_text, name.upper())
        fields[name] = value or ""
    return fields


def open_task_fields(args, brief_text, design_text):
    """Resolve the optional task.json fields from flags, then brief/design text."""
    return {
        "definition_of_done": args.definition
        or extract_section(brief_text, "DEFINITION OF DONE")
        or "",
        "task_text": args.task_text or extract_section(brief_text, "TASK"),
        "interface_contract": args.interface
        or extract_section(design_text, "INTERFACE CONTRACT"),
        "files": args.files or extract_section(design_text, "FILES"),
        "mentor": mentor_fields(args, brief_text),
    }


def build_task_doc(task, role, chunk_name, git, inputs, fields, design_name):
    """Assemble the task.json document for a freshly opened task."""
    roles = {seat: {"session": None, "loaded": False, "cursor": 0} for seat in SEATS}
    roles.setdefault(role, {"session": None, "loaded": False, "cursor": 0})
    doc = {
        "task": task,
        "created_at": iso_now(),
        "role": role,
        "chunk": chunk_name,
        "git": git,
        "inputs": inputs,
        "sealed": False,
        "roles": roles,
        "definition_of_done": fields["definition_of_done"],
        "mentor": fields["mentor"],
    }
    for key in ("task_text", "interface_contract", "files"):
        if fields[key]:
            doc[key] = fields[key]
    if design_name:
        doc["design_input"] = design_name
    return doc


def cmd_open(args):
    """Open a task: create dated layout, write task.json, first chunk, inputs, open journal entry."""
    root = args.root
    state = state_root(root)
    task = args.task
    role = args.role
    validate_task(task)
    validate_role(role)
    date_str = _today_str()

    ensure_locks(state)
    with lock(state, f"task-{task}"):
        if _task_json_path(state, task, date_str).is_file():
            raise TeamError([f"task `{task}` already exists for role `{role}`"])

        chunk_name = f"01-{role}"
        create_chunk_dirs(state, task, chunk_name, date_str)
        inputs = copy_chunk_inputs(
            root, args, _input_dir(state, task, chunk_name, date_str)
        )

        fields = open_task_fields(
            args, _read_text(args.brief), _read_text(args.design)
        )
        git = git_info(root)
        task_doc = build_task_doc(
            task,
            role,
            chunk_name,
            git,
            inputs,
            fields,
            Path(args.design).name if args.design else None,
        )
        write_json_atomic(_task_json_path(state, task, date_str), task_doc)

        record = {
            "seq": 1,
            "kind": "open",
            "at": iso_now(),
            "git": git,
            "inputs": inputs,
        }
        append_journal(state, task, chunk_name, record, date_str)

    emit(
        args,
        f"OPENED: {task}\nROLE: {role}\nCHUNK: {chunk_name}",
        {"command": "open", "task": task, "role": role, "chunk": chunk_name},
    )


def check_bind(task_doc, seat, session, takeover):
    """Validate a bind request and return the seat's previous session."""
    roles = task_doc.get("roles", {})
    task = task_doc.get("task", "")
    if seat not in roles:
        raise TeamError([f"seat `{seat}` is not part of task `{task}`"])
    for other_seat, other_info in roles.items():
        if other_info.get("session") == session and other_seat != seat:
            raise TeamError(
                [
                    f"session {session} is already bound to {task}/{other_seat}",
                    "a session may serve exactly one seat; use a fresh session",
                ]
            )
    previous = roles[seat].get("session")
    if previous and not takeover:
        raise TeamError(
            [
                f"seat `{seat}` is already bound to session {previous}",
                "only the operator may replace it; retry with --takeover after stopping it",
            ]
        )
    if previous == session:
        raise TeamError([f"seat `{seat}` is already bound to this session"])
    return previous


def cmd_bind(args):
    """Bind a session to a task's role seat."""
    root = args.root
    state = state_root(root)
    task = args.task
    seat = args.seat
    validate_task(task)
    validate_seat(seat)
    if not args.session:
        raise TeamError(["a session id is required to bind a seat"])

    ensure_locks(state)
    with lock(state, f"task-{task}"):
        date_str = _today_str()
        task_doc = load_task_json(state, task, date_str)
        previous = check_bind(task_doc, seat, args.session, args.takeover)

        info = task_doc["roles"][seat]
        info["session"] = args.session
        info["loaded"] = False
        info["cursor"] = 0
        write_json_atomic(_task_json_path(state, task, date_str), task_doc)

    verb = "REBOUND" if previous else "BOUND"
    emit(
        args,
        f"{verb}: {task} {seat}",
        {"command": "bind", "task": task, "seat": seat, "rebound": bool(previous)},
    )


def _prune_empty_parents(path, stop):
    """Remove empty directories from ``path`` up to (not including) ``stop``."""
    parent = path
    while parent != stop:
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        else:
            break


def cmd_close(args):
    """Close a task: with --preserve moves to done, without deletes it."""
    root = args.root
    state = state_root(root)
    task = args.task
    validate_task(task)
    date_str = _today_str()

    ensure_locks(state)
    with lock(state, f"task-{task}"):
        task_dir = _task_dir(state, task, date_str)
        if not task_dir.is_dir():
            raise TeamError([f"task `{task}` does not exist"])

        if args.preserve:
            done_dir = _done_date_dir(state, date_str) / task
            done_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(task_dir), str(done_dir))
        else:
            shutil.rmtree(str(task_dir))
            date_dir = _date_dir(state, date_str)
            _prune_empty_parents(task_dir.parent, date_dir)
            if date_dir.is_dir() and not any(date_dir.iterdir()):
                date_dir.rmdir()

    verb = "PRESERVED" if args.preserve else "CLOSED"
    emit(
        args,
        f"{verb}: {task}",
        {"command": "close", "task": task, "preserve": args.preserve},
    )


def input_files(directory):
    """Return the regular files in ``directory`` in name order."""
    if not directory.is_dir():
        return []
    return [path for path in sorted(directory.iterdir()) if path.is_file()]


def render_input_file(path):
    """Render one input file as payload lines, tolerating unreadable bytes."""
    lines = [f"--- {path.name} ---"]
    try:
        lines.append(path.read_text())
    except (OSError, UnicodeDecodeError):
        lines.append(f"<unreadable: {path.name}>")
    return lines


def chunk_input_payload(state, task, chunk_name, date_str=None):
    """Render the write-once input files as the chunk payload text."""
    files = input_files(_input_dir(state, task, chunk_name, date_str))
    if not files:
        return []
    lines = ["PACK: " + ", ".join(path.name for path in files)]
    for path in files:
        lines.extend(render_input_file(path))
    return lines


# --- deterministic coder payload -------------------------------------------

CODER_SECTION_HEADERS = (
    "TASK",
    "DEFINITION OF DONE",
    "RESOLVED PATHS",
    "INPUTS",
    "FEATURE",
    "INTERFACE CONTRACT",
    "FILES",
    "HOW TO RUN",
    "PRIOR ATTEMPT",
    "WHEN STUCK",
    "WHEN DONE",
)

NO_PRIOR_ATTEMPT = "no prior attempt"

WHEN_STUCK_POLICY = (
    "No attempt cap: keep the oracle loop running while progress is real.",
    "When the next change would be a guess, ask one question with the exact command, output, and file:line.",
    "Ask again after each brief; the pair keep talking until the path is clear.",
    "Never ask 'is my code correct'; the oracle answers that.",
    "Interface, scope, or dependency doubt: ask before guessing.",
)

WHEN_DONE_POLICY = (
    "Journal a RESULT digest and keep the mail pointer <= 300 characters.",
    "Hand off to refactorer with the digest pointer.",
    "Leave the tree dirty; do not commit.",
)

HOW_TO_RUN_TEMPLATE = (
    "persistent: cd {persistent} && PYTHONDONTWRITEBYTECODE=1 {python} -m pytest",
    "acceptance: {python} {acceptance}/run_acceptance.py",
    "lint: {pack}/tools/ruff4py {source} {persistent}",
)


def _section_header(line):
    """Return the normalized header text for a section-header line, else None."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#") or (
        stripped.startswith("**") and stripped.endswith("**")
    ):
        candidate = stripped.strip("#* ").strip()
        return candidate or None
    word = stripped.split(" (", 1)[0].strip()
    if word.isupper() and any(char.isalpha() for char in word):
        return word
    return None


def extract_section(text, header):
    """Return the body under a markdown-ish ``header`` section, or None."""
    if not text:
        return None
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if _section_header(line) == header:
            start = index + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if _section_header(line) is not None:
            break
        body.append(line)
    joined = "\n".join(body).strip()
    return joined or None


def _read_text(path):
    if not path:
        return None
    try:
        return Path(path).read_text()
    except (OSError, UnicodeDecodeError):
        return None


def _config_belongs_to_pack(resolved):
    """True when the resolved config is the pack's own, i.e. a self-hosted pack."""
    config_path = getattr(resolved, "config_path", None)
    pack_root = getattr(resolved, "pack_root", None)
    if not config_path or not pack_root:
        return False
    return Path(config_path).parent == Path(pack_root)


def _root_of_kind(entries, kind):
    for entry in entries:
        if entry.get("kind") == kind:
            return entry["root"]
    return None


def persistent_test_root(resolved):
    """Return the persistent root that holds this workspace's tests.

    A self-hosted pack runs its own tests from the harness-kind root; a wired
    project runs them from the project-kind root. The choice comes from the
    configured kind, never from probing the disk, so absent configured roots
    still resolve deterministically.
    """
    entries = resolved.persistent_tests
    if _config_belongs_to_pack(resolved):
        preferred = ("harness", "project")
    else:
        preferred = ("project", "harness")
    for kind in preferred:
        root = _root_of_kind(entries, kind)
        if root is not None:
            return root
    if entries:
        return entries[0]["root"]
    return None


def _text_lines(value):
    if value is None:
        return []
    if isinstance(value, str):
        return value.splitlines()
    return [str(item) for item in value]


def _task_lines(task_doc):
    lines = [str(task_doc.get("task", ""))]
    task_text = task_doc.get("task_text")
    if task_text:
        lines.extend(str(task_text).splitlines())
    return lines


def _read_input(input_dir, name):
    if not name:
        return None
    path = input_dir / name
    if not path.is_file():
        return None
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def _feature_lines(input_dir):
    if not input_dir.is_dir():
        return []
    for path in sorted(input_dir.iterdir()):
        if path.is_file() and path.suffix == ".feature":
            try:
                return path.read_text().splitlines()
            except (OSError, UnicodeDecodeError):
                return []
    return []


def _resolved_path_lines(resolved):
    persistent = persistent_test_root(resolved)
    persistent_text = str(persistent) if persistent is not None else "(none)"
    return [
        f"workspace root: {resolved.workspace_root}",
        f"state root: {resolved.state_root}",
        f"artifacts root: {resolved.artifacts_root}",
        f"hot tests root: {resolved.hot_tests}",
        f"persistent test root: {persistent_text}",
    ]


def _how_to_run_lines(resolved):
    persistent = persistent_test_root(resolved)
    persistent_text = str(persistent) if persistent is not None else "(none)"
    acceptance = str(persistent / "acceptance") if persistent is not None else "(none)"
    source = str(resolved.source_roots[0]) if resolved.source_roots else "(none)"
    return [
        line.format(
            persistent=persistent_text,
            acceptance=acceptance,
            python=sys.executable,
            pack=resolved.pack_root,
            source=source,
        )
        for line in HOW_TO_RUN_TEMPLATE
    ]


def render_sections(sections):
    """Render ``(header, body_lines)`` pairs as flat payload lines."""
    lines = []
    for header, body in sections:
        lines.append(header)
        lines.extend(body)
    return lines


def _prior_attempt_lines(output_dir):
    attempts = []
    if output_dir.is_dir():
        attempts = sorted(output_dir.glob("attempt-*.txt"))
    if not attempts:
        return [NO_PRIOR_ATTEMPT]
    lines = []
    for path in attempts:
        lines.append(f"--- {path.name} ---")
        try:
            lines.extend(path.read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            lines.append(f"<unreadable: {path.name}>")
    return lines


def coder_payload_lines(root, state, task, chunk_name, task_doc, date_str=None):
    """Render the deterministic coder payload as a list of lines."""
    input_dir = _input_dir(state, task, chunk_name, date_str)
    output_dir = _output_dir(state, task, chunk_name, date_str)
    resolved = wiring.load(start=root)
    design = _read_input(input_dir, task_doc.get("design_input"))
    interface_contract = design
    if interface_contract is None:
        interface_contract = task_doc.get("interface_contract")
    files = task_doc.get("files")
    if files is None:
        files = design
    sections = (
        ("TASK", _task_lines(task_doc)),
        ("DEFINITION OF DONE", _text_lines(task_doc.get("definition_of_done"))),
        ("RESOLVED PATHS", _resolved_path_lines(resolved)),
        ("INPUTS", _text_lines(task_doc.get("inputs"))),
        ("FEATURE", _feature_lines(input_dir)),
        ("INTERFACE CONTRACT", _text_lines(interface_contract)),
        ("FILES", _text_lines(files)),
        ("HOW TO RUN", _how_to_run_lines(resolved)),
        ("PRIOR ATTEMPT", _prior_attempt_lines(output_dir)),
        ("WHEN STUCK", list(WHEN_STUCK_POLICY)),
        ("WHEN DONE", list(WHEN_DONE_POLICY)),
    )
    return render_sections(sections)


# --- deterministic mentor payload ------------------------------------------

MENTOR_SYSTEM_PROMPT = (
    "You are the mentor seat. Advise from the task and chunk state below; "
    "answer the worker's ask with the failure evidence in view."
)

MENTOR_SECTION_HEADERS = ("GOAL", "RULES", "TRAIL", "ASK", "FAILURE")

NO_TRAIL = "no trail"
NO_ASK = "no ask"
NO_FAILURE = "no failure"


def _mentor_field(task_doc, name):
    mentor = task_doc.get("mentor") or {}
    return mentor.get(name) or ""


def _trail_entry_text(entry):
    """Render one worker journal entry as its kind and payload text."""
    payload = {
        key: value
        for key, value in entry.items()
        if key not in ("seq", "kind", "at")
    }
    if not payload:
        return str(entry.get("kind", ""))
    return f"{entry.get('kind', '')}: {json.dumps(payload, sort_keys=True)}"


def trail_lines(entries):
    """Render the worker journal entries in order, or the fixed no-trail line."""
    lines = [
        _trail_entry_text(entry)
        for entry in sorted(entries, key=lambda item: item.get("seq", 0))
        if entry.get("kind") in WORKER_KINDS
    ]
    return lines or [NO_TRAIL]


def _latest_stuck(entries):
    stuck = [entry for entry in entries if entry.get("kind") == "stuck"]
    if not stuck:
        return None
    return max(stuck, key=lambda entry: entry.get("seq", 0))


def _stuck_attempt_output(state, task, chunk_name, date_str, entry):
    refs = entry.get("refs") or []
    if not refs:
        return None
    path = _output_dir(state, task, chunk_name, date_str) / refs[0]
    if not path.is_file():
        return None
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def ask_text(entries):
    """Return the ASK body from the latest stuck message, or the fixed line."""
    stuck = _latest_stuck(entries)
    message = stuck.get("message") if stuck else None
    return str(message) if message else NO_ASK


def failure_text(state, task, chunk_name, date_str, entries):
    """Return the FAILURE body from the latest stuck evidence, or the fixed line."""
    stuck = _latest_stuck(entries)
    if not stuck:
        return NO_FAILURE
    evidence = stuck.get("failure") or stuck.get("evidence")
    if evidence:
        return str(evidence)
    output = _stuck_attempt_output(state, task, chunk_name, date_str, stuck)
    if output:
        return output
    return NO_FAILURE


def mentor_payload_lines(state, task, chunk_name, task_doc, date_str=None):
    """Render the deterministic mentor payload as a list of lines."""
    entries = read_journal(state, task, chunk_name, date_str)
    sections = (
        ("GOAL", _text_lines(_mentor_field(task_doc, "goal"))),
        ("RULES", _text_lines(_mentor_field(task_doc, "rules"))),
        ("TRAIL", trail_lines(entries)),
        ("ASK", _text_lines(_mentor_field(task_doc, "ask") or ask_text(entries))),
        (
            "FAILURE",
            _text_lines(
                _mentor_field(task_doc, "failure")
                or failure_text(state, task, chunk_name, date_str, entries)
            ),
        ),
    )
    return [MENTOR_SYSTEM_PROMPT, *render_sections(sections)]


def is_mentor_full(task_doc, role, delta):
    """A full call for the mentor seat gets the deterministic mentor payload."""
    return not delta and role == "mentor"


def cmd_pull(args):
    """Pull or resume the next item for a bound session."""
    if args.seat:
        validate_seat(args.seat)
    state, task, role, chunk_name, date_str = resolve_chunk(args, args.seat)
    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        if task_doc.get("sealed"):
            raise TeamError(["task is sealed; no further sends or pulls are allowed"])

        # check if already bound (resume)
        info = task_doc["roles"][role]
        if info.get("session") == args.session:
            emit(
                args,
                "\n".join(
                    [
                        f"TASK: {task}/{role}",
                        f"SEAT: {role}",
                        "RESUMED: yes",
                        "PAYLOAD:",
                    ]
                    + chunk_input_payload(state, task, chunk_name, date_str)
                ),
                {"command": "pull", "task": task, "seat": role, "resumed": True},
            )
            return

        # first pull: bind session
        info["session"] = args.session
        info["loaded"] = False
        info["cursor"] = 0
        write_json_atomic(_task_json_path(state, task, date_str), task_doc)

        emit(
            args,
            "\n".join(
                [
                    f"TASK: {task}/{role}",
                    f"SEAT: {role}",
                    "PAYLOAD:",
                ]
                + chunk_input_payload(state, task, chunk_name, date_str)
            ),
            {"command": "pull", "task": task, "seat": role, "resumed": False},
        )


def cmd_send(args):
    """Send a message from one seat to another."""
    validate_seat(args.to)
    if not args.message:
        raise TeamError(["--message is required"])
    state, task, seat, chunk_name, date_str = resolve_chunk(args)
    allowed = EDGES.get((seat, args.to))
    if allowed is None:
        raise TeamError([f"edge {seat} -> {args.to} is not allowed"])
    if allowed != args.kind:
        raise TeamError([f"edge {seat} -> {args.to} requires kind `{allowed}`"])
    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        if task_doc.get("sealed"):
            raise TeamError(["task is sealed; no further sends or pulls are allowed"])
        if args.kind == "ask":
            seq = next_journal_seq(state, task, chunk_name, date_str)
            record = {
                "seq": seq,
                "kind": "stuck",
                "at": iso_now(),
                "from": seat,
                "to": args.to,
                "message": args.message,
            }
            append_journal(state, task, chunk_name, record, date_str)

    emit(
        args,
        f"QUEUED: {args.kind}\nTO: {args.to}\nKIND: {args.kind}",
        {
            "command": "send",
            "task": task,
            "from": seat,
            "to": args.to,
            "kind": args.kind,
        },
    )


def cmd_done(args):
    """Mark the current task as done."""
    state, task, role, chunk_name, date_str = resolve_chunk(args)
    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        if task_doc.get("sealed"):
            raise TeamError(["task is sealed"])
        seq = next_journal_seq(state, task, chunk_name, date_str)
        record = {
            "seq": seq,
            "kind": "done",
            "at": iso_now(),
        }
        if args.result:
            record["result"] = args.result
        append_journal(state, task, chunk_name, record, date_str)
    lines = [f"COMPLETED: {task}/{role}"]
    lines.append("NO_TASK")
    emit(
        args,
        "\n".join(lines),
        {"command": "done", "task": task, "seat": role, "ready": False},
    )


def selected_entries(entries, info, delta):
    """Return the journal entries to deliver; delta needs a prior full load."""
    if not delta:
        return entries
    if not info.get("loaded"):
        raise TeamError(
            ["LOAD_REQUIRED: call team_context without --delta before using --delta"]
        )
    return entries[info.get("cursor", 0):]


def is_coder_full(task_doc, role, delta):
    """A full call for the worker seat of a coder task gets the coder payload."""
    return not delta and role == "worker" and task_doc.get("role") == "coder"


def record_advice(state, task, chunk_name, date_str, task_doc, role, info, entries, selected, delta):
    """Append the advice entry and advance the seat's delivery cursor."""
    seq = next_journal_seq(state, task, chunk_name, date_str)
    record = {
        "seq": seq,
        "kind": "advice",
        "at": iso_now(),
        "from": role,
        "mode": "delta" if delta else "full",
        "delivered": len(selected),
    }
    append_journal(state, task, chunk_name, record, date_str)
    info["loaded"] = True
    info["cursor"] = len(entries) + 1
    write_json_atomic(_task_json_path(state, task, date_str), task_doc)


def non_coder_context_lines(state, task, chunk_name, date_str, role, selected, delta):
    """Render the input-pack plus journal delivery used by non-coder roles."""
    mode = "delta" if delta else "full"
    lines = [f"CONTEXT: {task} seat {role} mode {mode}"]
    if not delta:
        lines.extend(chunk_input_payload(state, task, chunk_name, date_str))
    lines.append("JOURNAL:")
    for entry in selected:
        lines.append(json.dumps(entry, sort_keys=True))
    return lines


def cmd_context(args):
    """Deliver context to a bound session.

    A full call for a bound coder (the worker seat on a coder task) returns the
    deterministic 11-section payload; a full call for the mentor seat returns the
    deterministic 5-section mentor payload; every other call keeps the input-pack
    and journal delivery.
    """
    state, task, role, chunk_name, date_str = resolve_chunk(args)
    payload = None
    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        info = task_doc["roles"][role]
        entries = read_journal(state, task, chunk_name, date_str)
        selected = selected_entries(entries, info, args.delta)
        coder_full = is_coder_full(task_doc, role, args.delta)
        mentor_full = is_mentor_full(task_doc, role, args.delta)
        if coder_full:
            payload = coder_payload_lines(
                args.root, state, task, chunk_name, task_doc, date_str
            )
        elif mentor_full:
            payload = mentor_payload_lines(
                state, task, chunk_name, task_doc, date_str
            )
        record_advice(
            state, task, chunk_name, date_str, task_doc, role, info, entries,
            selected, args.delta,
        )

    mode = "delta" if args.delta else "full"
    data = {
        "command": "context",
        "task": task,
        "seat": role,
        "mode": mode,
        "delivered": len(selected),
    }
    if coder_full or mentor_full:
        emit(args, "\n".join(payload), data)
        return
    lines = non_coder_context_lines(
        state, task, chunk_name, date_str, role, selected, args.delta
    )
    emit(args, "\n".join(lines), data)


def cmd_attempt(args):
    """Run an oracle command and record the attempt."""
    root = args.root
    if not args.command:
        raise TeamError(["--command is required"])
    state, task, role, chunk_name, date_str = resolve_chunk(args)
    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        if task_doc.get("sealed"):
            raise TeamError(["task is sealed"])
        number = next_attempt_seq(state, task, chunk_name, date_str)

    cwd = Path(args.cwd) if args.cwd else Path(root)
    if not cwd.is_absolute():
        cwd = Path(root) / cwd
    if not cwd.is_dir():
        raise TeamError([f"cwd is not a directory: {cwd}"])

    exit_code, output, timed_out, duration = run_oracle(args.command, cwd, args.timeout)

    # write output files
    out_path = attempt_output_path(state, task, chunk_name, number, date_str)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output)
    refs = [f"attempt-{number:02d}.txt"]

    diff = git_diff(root)
    if diff:
        diff_file = attempt_diff_path(state, task, chunk_name, number, date_str)
        diff_file.write_text(diff)
        refs.append(f"attempt-{number:02d}.diff")

    # append attempt journal entry
    with lock(state, f"task-{task}"):
        seq = next_journal_seq(state, task, chunk_name, date_str)
        record = {
            "seq": seq,
            "kind": "attempt",
            "at": iso_now(),
            "attempt": number,
            "cmd": args.command,
            "cwd": str(cwd),
            "exit": exit_code,
            "duration_s": round(duration, 3),
            "timeout": timed_out,
            "refs": refs,
        }
        append_journal(state, task, chunk_name, record, date_str)

    lines = [
        f"ATTEMPT: {number}",
        f"EXIT: {exit_code}",
        f"CWD: {cwd}",
    ]
    if output:
        lines.append("--- output ---")
        lines.append(output)
    emit(args, "\n".join(lines), {"command": "attempt", "attempt": number, "exit": exit_code, "output": output})


def attach_attempt(entry, attempt, journal_entries):
    """Merge the fields of attempt ``attempt`` into ``entry``; fail if absent.

    The entry keeps its own bookkeeping fields (``seq``/``kind``/``at``) so an
    entry that references an attempt stays the kind the caller journaled.
    """
    for candidate in journal_entries:
        if candidate.get("kind") == "attempt" and candidate.get("attempt") == attempt:
            for key, value in candidate.items():
                if key in ("seq", "kind", "at"):
                    continue
                entry.setdefault(key, value)
            return
    raise TeamError([f"attempt artifact not found: attempt {attempt}"])


def cmd_journal(args):
    """Append a journal entry to the current chunk's journal."""
    validate_kind(args.kind)
    entry = parse_entry(args.entry)
    state, task, role, chunk_name, date_str = resolve_chunk(args)

    # worker kinds restricted to worker seat
    if args.kind in WORKER_KINDS and role != "worker":
        raise TeamError(["only the worker seat may append worker journal kinds"])

    with lock(state, f"task-{task}"):
        task_doc = load_task_json(state, task, date_str)
        if task_doc.get("sealed"):
            raise TeamError(["task is sealed"])

        if args.attempt is not None:
            attach_attempt(
                entry, args.attempt, read_journal(state, task, chunk_name, date_str)
            )

        seq = next_journal_seq(state, task, chunk_name, date_str)
        record = {"seq": seq, "kind": args.kind, "at": iso_now()}
        record.update(entry)
        append_journal(state, task, chunk_name, record, date_str)

    emit(
        args,
        f"JOURNALED: seq {seq} kind {args.kind}",
        {"command": "journal", "task": task, "seq": seq, "kind": args.kind},
    )


def task_docs(state):
    """Return every live task.json document, skipping corrupt ones."""
    tasks_dir = _tasks_root(state)
    if not tasks_dir.is_dir():
        return []
    found = []
    for date_dir in sorted(tasks_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        for task_dir in date_dir.iterdir():
            if not task_dir.is_dir():
                continue
            task_json = task_dir / "task.json"
            if not task_json.is_file():
                continue
            try:
                found.append(read_json(task_json))
            except (OSError, ValueError):
                continue
    return found


def ready_entries(found):
    """Return (task, seat, state) rows for every unsealed seat."""
    ready = []
    for doc in found:
        if doc.get("sealed"):
            continue
        for role, info in doc.get("roles", {}).items():
            seat_state = "SPAWN_PENDING" if not info.get("session") else "queued"
            ready.append((doc["task"], role, seat_state))
    return ready


def status_lines(found):
    """Render the human-readable per-task status block."""
    lines = []
    for doc in found:
        lines.append(f"TASK: {doc['task']}")
        lines.append(f"SEALED: {'yes' if doc.get('sealed') else 'no'}")
        for role, info in doc.get("roles", {}).items():
            lines.append(
                f"SEAT: {role} session {info.get('session') or '-'} "
                f"loaded {'yes' if info.get('loaded') else 'no'} "
                f"cursor {info.get('cursor', 0)}"
            )
    return lines


def cmd_status(args):
    """Show status of a task or all tasks."""
    found = task_docs(state_root(args.root))

    if args.ready:
        ready = ready_entries(found)
        lines = [f"READY: {task} {role} {seat_state}" for task, role, seat_state in ready]
        emit(args, "\n".join(lines) or "READY: none", {"command": "status", "ready": ready})
        return

    lines = status_lines(found)
    emit(args, "\n".join(lines) or "NO_TASKS", {"command": "status", "tasks": found})


# --- parser ----------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="team")
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--state-root")
    sub = parser.add_subparsers(dest="command", required=True)

    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("task")
    open_cmd.add_argument("--role", required=True)
    open_cmd.add_argument("--brief")
    open_cmd.add_argument("--feature")
    open_cmd.add_argument("--design")
    open_cmd.add_argument("--definition")
    open_cmd.add_argument("--task-text")
    open_cmd.add_argument("--interface")
    open_cmd.add_argument("--files")
    open_cmd.add_argument("--goal")
    open_cmd.add_argument("--rules")
    open_cmd.add_argument("--ask")
    open_cmd.add_argument("--failure")
    open_cmd.add_argument("--json", action="store_true")
    open_cmd.set_defaults(func=cmd_open)

    bind = sub.add_parser("bind")
    bind.add_argument("task")
    bind.add_argument("--seat", required=True)
    bind.add_argument("--session", required=True)
    bind.add_argument("--takeover", action="store_true")
    bind.add_argument("--json", action="store_true")
    bind.set_defaults(func=cmd_bind)

    status = sub.add_parser("status")
    status.add_argument("--ready", action="store_true")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    close = sub.add_parser("close")
    close.add_argument("task")
    close.add_argument("--preserve", action="store_true")
    close.add_argument("--json", action="store_true")
    close.set_defaults(func=cmd_close)

    pull = sub.add_parser("pull")
    pull.add_argument("--seat")
    pull.add_argument("--session", required=True)
    pull.add_argument("--json", action="store_true")
    pull.set_defaults(func=cmd_pull)

    send = sub.add_parser("send")
    send.add_argument("--to", required=True)
    send.add_argument("--kind", required=True)
    send.add_argument("--message", required=True)
    send.add_argument("--session", required=True)
    send.add_argument("--json", action="store_true")
    send.set_defaults(func=cmd_send)

    done = sub.add_parser("done")
    done.add_argument("--result")
    done.add_argument("--session", required=True)
    done.add_argument("--json", action="store_true")
    done.set_defaults(func=cmd_done)

    context = sub.add_parser("context")
    context.add_argument("--delta", action="store_true")
    context.add_argument("--session", required=True)
    context.add_argument("--json", action="store_true")
    context.set_defaults(func=cmd_context)

    journal = sub.add_parser("journal")
    journal.add_argument("--kind", required=True)
    journal.add_argument("--entry", required=True)
    journal.add_argument("--attempt", type=int)
    journal.add_argument("--session", required=True)
    journal.add_argument("--json", action="store_true")
    journal.set_defaults(func=cmd_journal)

    attempt = sub.add_parser("attempt")
    attempt.add_argument("--command", required=True)
    attempt.add_argument("--cwd")
    attempt.add_argument("--timeout", type=float)
    attempt.add_argument("--session", required=True)
    attempt.add_argument("--json", action="store_true")
    attempt.set_defaults(func=cmd_attempt)

    return parser


def main(argv=None):
    return run_cli(
        build_parser,
        TeamError,
        "TEAM",
        lambda args: set_state_root(args.state_root),
        argv,
    )


if __name__ == "__main__":
    sys.exit(main())
