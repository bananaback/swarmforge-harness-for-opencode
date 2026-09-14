#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import wiring
from durable_store import iso_now, list_json, read_json, run_cli, write_json_atomic
from durable_store import lock as store_lock
from durable_store import next_seq as store_next_seq

SEATS = ("worker", "mentor", "senior")
KINDS = ("readback", "plan", "result", "note")
STATES = ("new", "in_process", "completed")
EDGES = {
    ("worker", "mentor"): "ask",
    ("mentor", "worker"): "brief",
    ("mentor", "senior"): "escalate",
    ("senior", "mentor"): "decision",
}
CHUNK_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CHUNK_MAX = 80


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


def team_root(root):
    return state_root(root) / "team"


def chunk_dir(root, chunk):
    return team_root(root) / chunk


def roster_path(root, chunk):
    return chunk_dir(root, chunk) / "roster.json"


def pack_dir(root, chunk):
    return chunk_dir(root, chunk) / "pack"


def journal_path(root, chunk):
    return chunk_dir(root, chunk) / "journal.jsonl"


def attempts_dir(root, chunk):
    return chunk_dir(root, chunk) / "attempts"


def seat_dir(root, chunk, seat):
    return chunk_dir(root, chunk) / "seats" / seat


def seat_state_dir(root, chunk, seat, state):
    return seat_dir(root, chunk, seat) / state


def ensure_base(root):
    (team_root(root) / "locks").mkdir(parents=True, exist_ok=True)


def ensure_seat(root, chunk, seat):
    for state in STATES:
        seat_state_dir(root, chunk, seat, state).mkdir(parents=True, exist_ok=True)


# --- io --------------------------------------------------------------------


@contextmanager
def lock(root, name):
    ensure_base(root)
    digest = hashlib.sha256(name.encode()).hexdigest()[:16]
    with store_lock(team_root(root) / "locks", digest):
        yield


def list_seat(root, chunk, seat, state):
    return list_json(seat_state_dir(root, chunk, seat, state))


def next_seq(root, chunk):
    return store_next_seq(chunk_dir(root, chunk) / "seq")


# --- validation ------------------------------------------------------------


def chunk_problem(chunk):
    if not chunk:
        return "chunk must not be empty"
    if len(chunk) > CHUNK_MAX:
        return f"chunk must be at most {CHUNK_MAX} characters"
    if chunk.startswith("/") or chunk.endswith("/") or "\\" in chunk:
        return "chunk must be a relative path without empty segments"
    for segment in chunk.split("/"):
        if segment in (".", "..") or not CHUNK_SEGMENT_RE.match(segment):
            return (
                "chunk segments must start alphanumeric and contain only "
                "letters, digits, '.', '_', '-'"
            )
    return None


def validate_chunk(chunk):
    problem = chunk_problem(chunk)
    if problem:
        raise TeamError([problem])


def validate_seat(seat):
    if seat not in SEATS:
        raise TeamError([f"seat must be one of: {', '.join(SEATS)}"])


# --- pack / journal --------------------------------------------------------


def compute_pack_hash(pack):
    pack = Path(pack)
    entries = []
    if pack.is_dir():
        for path in sorted(pack.iterdir()):
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append((path.name, digest))
    material = "".join(f"{name}\0{digest}\n" for name, digest in entries)
    return hashlib.sha256(material.encode()).hexdigest(), [name for name, _ in entries]


def read_journal(root, chunk):
    path = journal_path(root, chunk)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def append_journal(root, chunk, entry):
    path = journal_path(root, chunk)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


# --- caller resolution -----------------------------------------------------


def is_roster(doc):
    return isinstance(doc, dict) and isinstance(doc.get("seats"), dict) and "chunk" in doc


def all_rosters(root):
    """Return ``(chunk, doc)`` for every readable, well-formed roster."""
    base = team_root(root)
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.rglob("roster.json")):
        try:
            doc = read_json(path)
        except (OSError, ValueError):
            continue
        if not is_roster(doc):
            continue
        chunk = str(path.parent.relative_to(base))
        found.append((chunk, doc))
    return found


def session_matches(root, session):
    matches = []
    for chunk, doc in all_rosters(root):
        for seat, info in doc.get("seats", {}).items():
            if info.get("session") == session:
                matches.append((chunk, seat))
    return matches


def resolve_binding(root, session, seat_hint=None):
    if not session:
        raise TeamError(["a session id is required for this operation"])
    matches = session_matches(root, session)
    if not matches:
        raise TeamError(
            [
                "session is not bound to any team seat; every "
                "coder/refactorer/architect dispatch runs inside a phase "
                "chunk, so an unbound call is an orchestrator binding failure",
                "STOP and report this exact error; never rationalize it away "
                "and continue",
            ]
        )
    if len(matches) > 1:
        raise TeamError(["session is bound to more than one seat; state is ambiguous"])
    chunk, seat = matches[0]
    if seat_hint and seat_hint != seat:
        raise TeamError([f"session is bound to `{seat}`, not `{seat_hint}`"])
    return chunk, seat


def load_roster(root, chunk):
    path = roster_path(root, chunk)
    if not path.is_file():
        raise TeamError([f"chunk `{chunk}` does not exist"])
    try:
        roster = read_json(path)
    except (OSError, ValueError) as error:
        raise TeamError([f"chunk `{chunk}` roster is corrupt: {error}"])
    if not is_roster(roster):
        raise TeamError([f"chunk `{chunk}` roster is corrupt"])
    return roster


def require_open(roster):
    if roster.get("sealed"):
        raise TeamError(["chunk is sealed; no further sends or pulls are allowed"])


# --- messages --------------------------------------------------------------


def build_chunk_payload(chunk, brief_ref, brief_content, pack_files):
    lines = [f"CHUNK: {chunk}"]
    if brief_ref:
        lines.append(f"BRIEF: {brief_ref}")
    if pack_files:
        lines.append("PACK: " + ", ".join(pack_files))
    if brief_content:
        lines.append("")
        lines.append(brief_content)
    return "\n".join(lines)


def make_message(chunk, sender, recipient, kind, message):
    now = iso_now()
    return {
        "id": uuid.uuid4().hex,
        "chunk": chunk,
        "from": sender,
        "to": recipient,
        "kind": kind,
        "message": message,
        "created_at": now,
        "enqueued_at": now,
        "dequeued_at": None,
        "completed_at": None,
        "owner_session": None,
        "result": None,
        "payload": message,
    }


def enqueue(root, chunk, seat, doc):
    ensure_seat(root, chunk, seat)
    seq = next_seq(root, chunk)
    doc["seq"] = seq
    name = f"{seq:08d}_{doc['id']}.json"
    write_json_atomic(seat_state_dir(root, chunk, seat, "new") / name, doc)
    return doc


def describe_task(root, chunk, seat, path, resumed):
    doc = read_json(path)
    lines = [f"TASK: {chunk}/{seat}", f"SEAT: {seat}", f"KIND: {doc['kind']}"]
    lines.append(f"FROM: {doc['from']}")
    if resumed:
        lines.append("RESUMED: yes")
    lines.append("PAYLOAD:")
    lines.append(doc.get("payload") or doc.get("message") or "")
    return "\n".join(lines)


# --- commands --------------------------------------------------------------


def emit(args, human, data):
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(human)


def cmd_open(args):
    root = args.root
    chunk = args.chunk
    validate_chunk(chunk)
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        if roster_path(root, chunk).exists():
            raise TeamError([f"chunk `{chunk}` already exists"])
        pack = pack_dir(root, chunk)
        pack.mkdir(parents=True, exist_ok=True)
        if args.pack:
            source = Path(args.pack)
            if not source.is_dir():
                raise TeamError([f"pack directory not found: {args.pack}"])
            for path in sorted(source.iterdir()):
                if path.is_file():
                    (pack / path.name).write_bytes(path.read_bytes())
        pack_hash, pack_files = compute_pack_hash(pack)
        roster = {
            "chunk": chunk,
            "sealed": False,
            "created_at": iso_now(),
            "pack_hash": pack_hash,
            "pack_files": pack_files,
            "seats": {
                seat: {"session": None, "loaded": False, "cursor": 0, "takeovers": []}
                for seat in SEATS
            },
        }
        write_json_atomic(roster_path(root, chunk), roster)
        brief_content = None
        if args.brief:
            brief_path = Path(args.brief)
            if brief_path.is_file():
                brief_content = brief_path.read_text()
        payload = build_chunk_payload(chunk, args.brief, brief_content, pack_files)
        doc = make_message(chunk, "orchestrator", "worker", "chunk", payload)
        enqueue(root, chunk, "worker", doc)
    lines = [f"OPENED: {chunk}", f"PACK: {pack_hash}", "SEEDED: worker"]
    emit(
        args,
        "\n".join(lines),
        {"command": "open", "chunk": chunk, "pack_hash": pack_hash, "seeded": "worker"},
    )


def cmd_bind(args):
    root = args.root
    chunk = args.chunk
    validate_chunk(chunk)
    validate_seat(args.seat)
    if not args.session:
        raise TeamError(["a session id is required to bind a seat"])
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        require_open(roster)
        for other_chunk, other_seat in session_matches(root, args.session):
            if (other_chunk, other_seat) != (chunk, args.seat):
                raise TeamError(
                    [
                        f"session {args.session} is already bound to "
                        f"{other_chunk}/{other_seat}",
                        "a session may serve exactly one seat; use a fresh session",
                    ]
                )
        info = roster["seats"][args.seat]
        previous = info["session"]
        if previous and not args.takeover:
            raise TeamError(
                [
                    f"seat `{args.seat}` is already bound to session {previous}",
                    "only the operator may replace it; retry with --takeover after stopping it",
                ]
            )
        if previous == args.session:
            raise TeamError([f"seat `{args.seat}` is already bound to this session"])
        if previous:
            info.setdefault("takeovers", []).append(
                {"from": previous, "to": args.session, "at": iso_now()}
            )
        info["session"] = args.session
        info["loaded"] = False
        info["cursor"] = 0
        write_json_atomic(roster_path(root, chunk), roster)
    verb = "REBOUND" if previous else "BOUND"
    emit(
        args,
        f"{verb}: {chunk} {args.seat}",
        {"command": "bind", "chunk": chunk, "seat": args.seat, "rebound": bool(previous)},
    )


def seat_status(root, chunk, seat, roster):
    info = roster["seats"].get(seat, {})
    paths = {state: list_seat(root, chunk, seat, state) for state in STATES}
    counts = {state: len(state_paths) for state, state_paths in paths.items()}
    holders = []
    for path in paths["in_process"]:
        doc = read_json(path)
        holders.append(
            {"id": doc["id"], "owner": doc.get("owner_session"), "kind": doc["kind"]}
        )
    return {
        "session": info.get("session"),
        "loaded": info.get("loaded", False),
        "cursor": info.get("cursor", 0),
        "counts": counts,
        "in_process": holders,
    }


def chunk_status(root, chunk, roster):
    seats = {seat: seat_status(root, chunk, seat, roster) for seat in SEATS}
    return {"sealed": roster.get("sealed", False), "seats": seats}


def ready_entries(chunk, entry):
    if entry["sealed"]:
        return []
    entries = []
    for seat in SEATS:
        info = entry["seats"][seat]
        if info["counts"]["new"]:
            state = "queued" if info["session"] else "SPAWN_PENDING"
            entries.append((chunk, seat, state))
    return entries


def format_ready(ready, single_chunk):
    if single_chunk:
        lines = [f"READY: {seat} {state}" for _, seat, state in ready]
    else:
        lines = [f"READY: {chunk} {seat} {state}" for chunk, seat, state in ready]
    return lines or ["READY: none"]


def format_status(chunks, report):
    lines = []
    for chunk in chunks:
        entry = report[chunk]
        lines.append(f"CHUNK: {chunk}")
        lines.append(f"SEALED: {'yes' if entry['sealed'] else 'no'}")
        for seat in SEATS:
            info = entry["seats"][seat]
            counts = info["counts"]
            lines.append(
                f"SEAT: {seat} session {info['session'] or '-'} "
                f"loaded {'yes' if info['loaded'] else 'no'} cursor {info['cursor']} "
                f"new {counts['new']} in_process {counts['in_process']} "
                f"completed {counts['completed']}"
            )
            for item in info["in_process"]:
                lines.append(
                    f"HOLDER: {seat} owner {item['owner'] or '-'} "
                    f"kind {item['kind']} id {item['id']}"
                )
    return lines


def cmd_status(args):
    root = args.root
    if args.chunk:
        validate_chunk(args.chunk)
        rosters = [(args.chunk, load_roster(root, args.chunk))]
    else:
        rosters = all_rosters(root)
    chunks = [chunk for chunk, _ in rosters]
    report = {chunk: chunk_status(root, chunk, roster) for chunk, roster in rosters}
    ready = [entry for chunk in chunks for entry in ready_entries(chunk, report[chunk])]

    if args.ready:
        emit(
            args,
            "\n".join(format_ready(ready, bool(args.chunk))),
            {"command": "status", "ready": ready},
        )
        return

    emit(
        args,
        "\n".join(format_status(chunks, report)),
        {"command": "status", "chunks": report},
    )


def cmd_close(args):
    root = args.root
    chunk = args.chunk
    validate_chunk(chunk)
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        roster["sealed"] = True
        roster["closed_at"] = iso_now()
        write_json_atomic(roster_path(root, chunk), roster)
    emit(args, f"CLOSED: {chunk}", {"command": "close", "chunk": chunk, "sealed": True})


def cmd_pull(args):
    root = args.root
    if args.seat:
        validate_seat(args.seat)
    chunk, seat = resolve_binding(root, args.session, args.seat)
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        require_open(roster)
        current_hash, _ = compute_pack_hash(pack_dir(root, chunk))
        if current_hash != roster.get("pack_hash"):
            raise TeamError(
                [
                    f"pack for `{chunk}` was edited after open",
                    "the pack is sealed; the pull is refused",
                ]
            )
        in_process = list_seat(root, chunk, seat, "in_process")
        if len(in_process) > 1:
            raise TeamError(
                [
                    f"seat `{seat}` has more than one in-process item; resume is ambiguous",
                    "state is owned by the tool; do not repair files by hand",
                ]
            )
        if len(in_process) == 1:
            path = in_process[0]
            doc = read_json(path)
            if doc.get("owner_session") != args.session:
                doc.setdefault("takeovers", []).append(
                    {
                        "from": doc.get("owner_session") or "none",
                        "to": args.session,
                        "at": iso_now(),
                    }
                )
                doc["owner_session"] = args.session
                write_json_atomic(path, doc)
            emit(
                args,
                describe_task(root, chunk, seat, path, True),
                {"command": "pull", "chunk": chunk, "seat": seat, "resumed": True},
            )
            return
        queued = list_seat(root, chunk, seat, "new")
        if not queued:
            emit(
                args,
                "NO_TASK",
                {"command": "pull", "chunk": chunk, "seat": seat, "state": "no_task"},
            )
            return
        source = queued[0]
        target = seat_state_dir(root, chunk, seat, "in_process") / source.name
        if target.exists():
            raise TeamError([f"claim target already exists: {target.name}"])
        os.replace(source, target)
        doc = read_json(target)
        doc["dequeued_at"] = iso_now()
        doc["owner_session"] = args.session
        write_json_atomic(target, doc)
        emit(
            args,
            describe_task(root, chunk, seat, target, False),
            {"command": "pull", "chunk": chunk, "seat": seat, "resumed": False},
        )


def cmd_send(args):
    root = args.root
    validate_seat(args.to)
    chunk, seat = resolve_binding(root, args.session)
    if not args.message:
        raise TeamError(["--message is required"])
    allowed = EDGES.get((seat, args.to))
    if allowed is None:
        raise TeamError([f"edge {seat} -> {args.to} is not allowed"])
    if allowed != args.kind:
        raise TeamError([f"edge {seat} -> {args.to} requires kind `{allowed}`"])
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        require_open(roster)
        doc = make_message(chunk, seat, args.to, args.kind, args.message)
        enqueue(root, chunk, args.to, doc)
    emit(
        args,
        f"QUEUED: {doc['id']}\nTO: {args.to}\nKIND: {args.kind}",
        {
            "command": "send",
            "chunk": chunk,
            "from": seat,
            "to": args.to,
            "kind": args.kind,
            "id": doc["id"],
        },
    )


def select_in_process(root, chunk, seat, item_id):
    in_process = list_seat(root, chunk, seat, "in_process")
    if not in_process:
        raise TeamError([f"no in-process item for seat `{seat}`"])
    if not item_id:
        return in_process
    selected = [p for p in in_process if read_json(p).get("id") == item_id]
    if not selected:
        raise TeamError([f"item `{item_id}` is not in process for seat `{seat}`"])
    return selected


def complete_item(root, chunk, seat, path, session, result):
    doc = read_json(path)
    owner = doc.get("owner_session")
    if owner not in (None, session):
        raise TeamError([f"item is owned by session {owner}; refusing to complete"])
    doc["completed_at"] = iso_now()
    if result:
        doc["result"] = result
    write_json_atomic(path, doc)
    target = seat_state_dir(root, chunk, seat, "completed") / path.name
    if target.exists():
        raise TeamError([f"completed target already exists: {target.name}"])
    os.replace(path, target)


def cmd_done(args):
    root = args.root
    chunk, seat = resolve_binding(root, args.session)
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        require_open(load_roster(root, chunk))
        selected = select_in_process(root, chunk, seat, args.id)
        for path in selected:
            complete_item(root, chunk, seat, path, args.session, args.result)
        waiting = bool(list_seat(root, chunk, seat, "new"))
    lines = [f"COMPLETED: {chunk}/{seat}"]
    lines.append("READY" if waiting else "NO_TASK")
    emit(
        args,
        "\n".join(lines),
        {"command": "done", "chunk": chunk, "seat": seat, "ready": waiting},
    )


def cmd_context(args):
    root = args.root
    chunk, seat = resolve_binding(root, args.session)
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        info = roster["seats"][seat]
        entries = read_journal(root, chunk)
        if args.delta:
            if not info.get("loaded"):
                raise TeamError(
                    [
                        "LOAD_REQUIRED: call team_context without --delta before using --delta"
                    ]
                )
            selected = entries[info.get("cursor", 0):]
        else:
            selected = entries
        info["loaded"] = True
        info["cursor"] = len(entries)
        write_json_atomic(roster_path(root, chunk), roster)
    mode = "delta" if args.delta else "full"
    lines = [f"CONTEXT: {chunk} seat {seat} mode {mode}"]
    if not args.delta:
        lines.append("PACK:")
        directory = pack_dir(root, chunk)
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                if path.is_file():
                    lines.append(f"--- {path.name} ---")
                    lines.append(path.read_text())
    lines.append("JOURNAL:")
    for entry in selected:
        lines.append(json.dumps(entry, sort_keys=True))
    emit(
        args,
        "\n".join(lines),
        {
            "command": "context",
            "chunk": chunk,
            "seat": seat,
            "mode": mode,
            "delivered": len(selected),
        },
    )


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


def read_attempt(root, chunk, number):
    path = attempts_dir(root, chunk) / f"{number:02d}.json"
    if not path.is_file():
        raise TeamError([f"attempt artifact not found: {path.name}"])
    doc = read_json(path)
    if not isinstance(doc, dict):
        raise TeamError([f"attempt artifact {path.name} must be a JSON object"])
    return doc


def run_oracle(command, cwd, timeout):
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output, False, time.monotonic() - started
    except subprocess.TimeoutExpired as error:
        output = ""
        for stream in (error.stdout, error.stderr):
            if isinstance(stream, bytes):
                output += stream.decode(errors="replace")
            elif stream:
                output += stream
        return 124, output, True, time.monotonic() - started


def git_diff(root):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def record_attempt(root, chunk, number, command, cwd, exit_code, output, duration, timed_out):
    directory = attempts_dir(root, chunk)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{number:02d}"
    (directory / f"{stem}.output.txt").write_text(output)
    refs = [f"{stem}.output.txt"]
    diff = git_diff(root)
    if diff:
        (directory / f"{stem}.diff").write_text(diff)
        refs.append(f"{stem}.diff")
    doc = {
        "attempt": number,
        "cmd": command,
        "cwd": str(cwd),
        "exit": exit_code,
        "duration_s": round(duration, 3),
        "timeout": timed_out,
        "refs": refs,
        "recorded_at": iso_now(),
    }
    write_json_atomic(directory / f"{stem}.json", doc)
    return doc


def cmd_attempt(args):
    root = args.root
    chunk, seat = resolve_binding(root, args.session)
    if seat != "worker":
        raise TeamError(["only the worker seat may record an oracle attempt"])
    if not args.command:
        raise TeamError(["--command is required"])
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        require_open(load_roster(root, chunk))
        number = store_next_seq(attempts_dir(root, chunk) / ".seq")
    cwd = Path(args.cwd) if args.cwd else Path(root)
    if not cwd.is_absolute():
        cwd = Path(root) / cwd
    if not cwd.is_dir():
        raise TeamError([f"cwd is not a directory: {cwd}"])
    exit_code, output, timed_out, duration = run_oracle(args.command, cwd, args.timeout)
    doc = record_attempt(
        root, chunk, number, args.command, cwd, exit_code, output, duration, timed_out
    )
    lines = [
        f"ATTEMPT: {number}",
        f"EXIT: {exit_code}",
        f"CWD: {cwd}",
    ]
    if output:
        lines.append("--- output ---")
        lines.append(output)
    emit(args, "\n".join(lines), {"command": "attempt", **doc, "output": output})


def cmd_journal(args):
    root = args.root
    if args.kind not in KINDS:
        raise TeamError([f"kind must be one of: {', '.join(KINDS)}"])
    entry = parse_entry(args.entry)
    chunk, seat = resolve_binding(root, args.session)
    if seat != "worker":
        raise TeamError(["only the worker seat may append to the journal"])
    ensure_base(root)
    with lock(root, f"chunk-{chunk}"):
        roster = load_roster(root, chunk)
        require_open(roster)
        if args.attempt is not None:
            for key, value in read_attempt(root, chunk, args.attempt).items():
                entry.setdefault(key, value)
        seq = len(read_journal(root, chunk)) + 1
        record = {"seq": seq, "kind": args.kind, "at": iso_now()}
        record.update(entry)
        append_journal(root, chunk, record)
    emit(
        args,
        f"JOURNALED: seq {seq} kind {args.kind}",
        {"command": "journal", "chunk": chunk, "seq": seq, "kind": args.kind},
    )


# --- parser ----------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="team")
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--state-root")
    sub = parser.add_subparsers(dest="command", required=True)

    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("chunk")
    open_cmd.add_argument("--brief")
    open_cmd.add_argument("--pack")
    open_cmd.add_argument("--json", action="store_true")
    open_cmd.set_defaults(func=cmd_open)

    bind = sub.add_parser("bind")
    bind.add_argument("chunk")
    bind.add_argument("--seat", required=True)
    bind.add_argument("--session", required=True)
    bind.add_argument("--takeover", action="store_true")
    bind.add_argument("--json", action="store_true")
    bind.set_defaults(func=cmd_bind)

    status = sub.add_parser("status")
    status.add_argument("chunk", nargs="?")
    status.add_argument("--ready", action="store_true")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    close = sub.add_parser("close")
    close.add_argument("chunk")
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
    done.add_argument("--id")
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
