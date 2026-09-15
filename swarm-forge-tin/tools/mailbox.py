#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import wiring
from durable_store import iso_now, list_json, read_json, run_cli, write_json_atomic
from durable_store import lock as store_lock
from durable_store import next_seq as store_next_seq

BUILTIN_SENDERS = ("build", "plan")
STATES = ("new", "in_process", "completed", "failed")
TYPES = ("handoff", "note")
ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
PRIORITY_RE = re.compile(r"^[0-9]{2}$")
TASK_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._-]*"
TASK_RE = re.compile(rf"^{TASK_SEGMENT}(?:/{TASK_SEGMENT})*$")
TASK_MAX = 80
NOTE_MAX = 80
DETAIL_MAX = 300


class MailError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def age_seconds(stamp):
    if not stamp:
        return None
    try:
        then = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return max(0, int((datetime.now(timezone.utc) - then).total_seconds()))


def format_age(seconds):
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


_STATE_ROOT_OVERRIDE = None


def set_state_root(value):
    global _STATE_ROOT_OVERRIDE
    _STATE_ROOT_OVERRIDE = value


def state_root(root):
    return wiring.state_root_for(root, override=_STATE_ROOT_OVERRIDE)


def mail_root(root):
    return state_root(root) / "mail"


def inbox_dir(root, role):
    return mail_root(root) / "inbox" / role


def ensure_base(root):
    (mail_root(root) / "locks").mkdir(parents=True, exist_ok=True)
    (mail_root(root) / "counters").mkdir(parents=True, exist_ok=True)


def ensure_role(root, role):
    for state in STATES:
        (inbox_dir(root, role) / state).mkdir(parents=True, exist_ok=True)


def discover_roles(root):
    roles = set(wiring.load(start=root).roles)
    agents = Path(root).resolve() / ".opencode" / "agents"
    if agents.is_dir():
        roles.update(p.stem for p in agents.glob("*.md"))
    inbox = mail_root(root) / "inbox"
    if inbox.is_dir():
        roles.update(p.name for p in inbox.iterdir() if p.is_dir())
    return sorted(roles)


@contextmanager
def lock(root, name):
    ensure_base(root)
    with store_lock(mail_root(root) / "locks", name):
        yield


def list_mail(root, role, state):
    return list_json(inbox_dir(root, role) / state)


def read_item(path):
    """Read a mail item, failing closed when its JSON is unreadable."""
    try:
        return read_json(path)
    except (OSError, ValueError) as error:
        raise MailError([f"mail item `{path.name}` is corrupt: {error}"])


def next_seq(root):
    return store_next_seq(mail_root(root) / "counters" / "seq")


def message_hash(sender, mtype, task, message):
    material = json.dumps(
        {
            "from": sender,
            "type": mtype,
            "task": task,
            "message": message,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode()).hexdigest()


def build_payload(doc):
    lines = []
    if doc["type"] == "handoff":
        lines.append(f"handoff for task: {doc['task']}")
    if doc.get("message"):
        if lines:
            lines.append("")
        lines.append(doc["message"])
    return "\n".join(lines)


def find_active(root, role, digest):
    for state in ("new", "in_process"):
        for path in list_mail(root, role, state):
            doc = read_item(path)
            if doc.get("content_hash") == digest:
                return doc["id"]
    return None


def _validate_sender(roles, sender, problems):
    if not ROLE_RE.match(sender or ""):
        problems.append("sender must be a lowercase role name")
    elif roles and sender not in roles and sender not in BUILTIN_SENDERS:
        problems.append(
            f"unknown sender `{sender}`; known roles: {', '.join(roles)}"
        )


def _validate_recipients(roles, raw, problems):
    recipients = [r.strip() for r in (raw or "").split(",") if r.strip()]
    if not recipients:
        problems.append("`to` must list at least one recipient role")
    for role in recipients:
        if not ROLE_RE.match(role):
            problems.append(f"recipient `{role}` must be a lowercase role name")
        elif roles and role not in roles:
            problems.append(
                f"unknown recipient `{role}`; known roles: {', '.join(roles)}"
            )
    if len(set(recipients)) != len(recipients):
        problems.append("`to` must not repeat a recipient")
    return recipients


def _validate_priority(priority, problems):
    if not PRIORITY_RE.match(priority or ""):
        problems.append(
            f"`priority` must be two digits from 00 to 99; got `{priority}`"
        )


def _validate_type(mtype, problems):
    if mtype not in TYPES:
        problems.append(f"`type` must be one of: {', '.join(TYPES)}")


def _validate_message(mtype, message, problems):
    if message is not None and "\n" in message:
        problems.append("`message` must be one line")
    if mtype == "note":
        if not message:
            problems.append("`note` requires a `message`")
        elif len(message) > NOTE_MAX:
            problems.append(f"`note` message must be at most {NOTE_MAX} characters")
    elif message and len(message) > DETAIL_MAX:
        problems.append(
            f"`handoff` message must be at most {DETAIL_MAX} characters"
        )


def _validate_task(mtype, task, problems):
    if mtype != "handoff":
        return
    if not task:
        problems.append("`handoff` requires a `task` name")
    elif len(task) > TASK_MAX:
        problems.append(f"`task` must be at most {TASK_MAX} characters")
    elif not TASK_RE.match(task):
        problems.append(
            "`task` segments must start alphanumeric and contain only "
            "letters, digits, `.`, `_`, `-`, separated by `/`"
        )


def validate_send(root, args):
    problems = []
    roles = discover_roles(root)
    _validate_sender(roles, args.sender, problems)
    recipients = _validate_recipients(roles, args.to, problems)
    _validate_priority(args.priority, problems)
    _validate_type(args.mtype, problems)
    _validate_message(args.mtype, args.message, problems)
    _validate_task(args.mtype, args.task, problems)
    if problems:
        raise MailError(problems)
    return recipients


def emit(args, human, data):
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(human)


def cmd_send(args):
    root = args.root
    recipients = validate_send(root, args)
    digest = message_hash(args.sender, args.mtype, args.task, args.message)
    ensure_base(root)
    with lock(root, "send"):
        duplicates = {}
        live = []
        for role in recipients:
            existing = find_active(root, role, digest)
            if existing:
                duplicates[role] = existing
            else:
                live.append(role)
        new_id = None
        if live:
            seq = next_seq(root)
            new_id = f"{utc_stamp()}_{seq:06d}_from_{args.sender}"
            now = iso_now()
            for role in live:
                ensure_role(root, role)
                doc = {
                    "id": new_id,
                    "from": args.sender,
                    "to": recipients,
                    "recipient": role,
                    "priority": args.priority,
                    "type": args.mtype,
                    "task": args.task,
                    "message": args.message,
                    "content_hash": digest,
                    "version": 1,
                    "created_at": now,
                    "enqueued_at": now,
                    "dequeued_at": None,
                    "completed_at": None,
                    "result": None,
                    "sender_session": args.session,
                    "owner_session": None,
                    "batch_id": None,
                    "payload": None,
                }
                doc["payload"] = build_payload(doc)
                target = inbox_dir(root, role) / "new" / f"{args.priority}_{new_id}.json"
                write_json_atomic(target, doc)
    lines = []
    if new_id:
        lines.append(f"QUEUED: {new_id}")
        lines.append(f"TO: {', '.join(live)}")
        lines.append(f"TYPE: {args.mtype}")
        lines.append(f"PRIORITY: {args.priority}")
        if args.task:
            lines.append(f"TASK_NAME: {args.task}")
    for role, mail_id in sorted(duplicates.items()):
        lines.append(f"DUPLICATE: {role} already has {mail_id}")
    if not lines:
        lines.append("NO_MAIL")
    emit(
        args,
        "\n".join(lines),
        {
            "command": "send",
            "id": new_id,
            "queued": live,
            "duplicates": duplicates,
        },
    )


def describe_task(root, path, resumed):
    doc = read_item(path)
    rel = os.path.relpath(path, str(Path(root).resolve()))
    lines = [f"TASK: {rel}"]
    lines.append(f"FROM: {doc['from']}")
    lines.append(f"TYPE: {doc['type']}")
    lines.append(f"PRIORITY: {doc['priority']}")
    if doc.get("task"):
        lines.append(f"TASK_NAME: {doc['task']}")
    if resumed:
        lines.append("RESUMED: yes")
    lines.append("PAYLOAD:")
    lines.append(doc.get("payload") or build_payload(doc))
    return "\n".join(lines)


def describe_batch(root, role, paths):
    rel = os.path.relpath(inbox_dir(root, role) / "in_process", str(Path(root).resolve()))
    top = read_item(paths[0])
    lines = [f"BATCH: {rel}", f"COUNT: {len(paths)}", f"PRIORITY: {top['priority']}"]
    items = []
    for path in paths:
        doc = read_item(path)
        item = os.path.relpath(path, str(Path(root).resolve()))
        lines.append(f"BATCH_ITEM: {item}")
        lines.append(f"FROM: {doc['from']}")
        lines.append(f"TYPE: {doc['type']}")
        if doc.get("task"):
            lines.append(f"TASK_NAME: {doc['task']}")
        lines.append("PAYLOAD:")
        lines.append(doc.get("payload") or build_payload(doc))
        items.append(doc["id"])
    return "\n".join(lines), items


def item_owner(doc):
    return doc.get("owner_session")


def refuse_other_owner(role, doc, args, kind):
    owner = item_owner(doc)
    if owner is None:
        return
    if args.session and args.session == owner:
        return
    if args.takeover:
        return
    raise MailError(
        [
            f"`{role}` {kind} is owned by session {owner}; refusing to continue",
            "only the owning session may resume or complete this item",
            f"ask the operator; if the operator confirms session {owner} is stopped, retry with takeover: true",
        ]
    )


def assign_owner(doc, session, takeover):
    previous = item_owner(doc)
    target = session or ("manual" if takeover else None)
    if target is None or previous == target:
        return False
    if previous is not None or takeover:
        doc.setdefault("takeovers", []).append(
            {"from": previous or "none", "to": target, "at": iso_now()}
        )
    doc["owner_session"] = target
    return True


def _resume_task(root, role, args):
    in_process = list_mail(root, role, "in_process")
    if len(in_process) > 1:
        raise MailError(
            [
                f"{role} has more than one in-process item; resume is ambiguous",
                "queue state is owned by the tool; do not repair files by hand",
            ]
        )
    if not in_process:
        return False
    path = in_process[0]
    doc = read_item(path)
    refuse_other_owner(role, doc, args, "in-process item")
    if assign_owner(doc, args.session, args.takeover):
        write_json_atomic(path, doc)
    emit(
        args,
        describe_task(root, path, True),
        {
            "command": "pull",
            "state": "task",
            "id": doc["id"],
            "resumed": True,
            "path": os.path.relpath(path, str(Path(root).resolve())),
        },
    )
    return True


def _group_batch(root, role):
    groups = {}
    for path in list_mail(root, role, "in_process"):
        doc = read_item(path)
        key = doc.get("batch_id") or doc["id"]
        groups.setdefault(key, []).append(path)
    if len(groups) > 1:
        raise MailError(
            [
                f"{role} has more than one in-process batch; resume is ambiguous",
                "queue state is owned by the tool; do not repair files by hand",
            ]
        )
    return groups


def _reassign_batch(root, role, paths, args):
    docs = [read_item(p) for p in paths]
    owners = {item_owner(d) for d in docs} - {None}
    if len(owners) > 1:
        raise MailError(
            [
                f"`{role}` batch has mixed ownership; resume is ambiguous",
                "queue state is owned by the tool; do not repair files by hand",
            ]
        )
    for doc in docs:
        refuse_other_owner(role, doc, args, "batch")
    for path, doc in zip(paths, docs):
        if assign_owner(doc, args.session, args.takeover):
            write_json_atomic(path, doc)
    return docs


def _resume_batch(root, role, args):
    groups = _group_batch(root, role)
    if not groups:
        return False
    key, paths = next(iter(groups.items()))
    paths = sorted(paths + sweep_batch(root, role, key))
    _reassign_batch(root, role, paths, args)
    human, items = describe_batch(root, role, paths)
    emit(
        args,
        human,
        {"command": "pull", "state": "batch", "ids": items, "resumed": True},
    )
    return True


def _claim_task(root, role, args, queued):
    source = queued[0]
    doc = read_item(source)
    target = inbox_dir(root, role) / "in_process" / source.name
    if target.exists():
        raise MailError([f"claim target already exists: {target}"])
    os.replace(source, target)
    doc["dequeued_at"] = iso_now()
    if args.session:
        doc["owner_session"] = args.session
    write_json_atomic(target, doc)
    emit(
        args,
        describe_task(root, target, False),
        {
            "command": "pull",
            "state": "task",
            "id": doc["id"],
            "resumed": False,
            "path": os.path.relpath(target, str(Path(root).resolve())),
        },
    )


def _claim_batch(root, role, args, queued):
    priority = queued[0].name.split("_", 1)[0]
    selected = [p for p in queued if p.name.split("_", 1)[0] == priority]
    batch_id = f"batch_{selected[0].name[:-5]}"
    now = iso_now()
    for path in selected:
        doc = read_item(path)
        doc["batch_id"] = batch_id
        doc["dequeued_at"] = now
        if args.session:
            doc["owner_session"] = args.session
        write_json_atomic(path, doc)
    moved = []
    for path in selected:
        target = inbox_dir(root, role) / "in_process" / path.name
        if target.exists():
            raise MailError([f"claim target already exists: {target}"])
        os.replace(path, target)
        moved.append(target)
    human, items = describe_batch(root, role, sorted(moved))
    emit(
        args,
        human,
        {"command": "pull", "state": "batch", "ids": items, "resumed": False},
    )


def _claim_queued(root, role, args):
    queued = list_mail(root, role, "new")
    if not queued:
        emit(args, "NO_TASK", {"command": "pull", "state": "no_task", "resumed": False})
        return
    if args.mode == "task":
        _claim_task(root, role, args, queued)
    else:
        _claim_batch(root, role, args, queued)


def cmd_pull(args):
    root = args.root
    role = args.role
    ensure_base(root)
    ensure_role(root, role)
    with lock(root, f"role-{role}"):
        if args.mode == "task":
            handled = _resume_task(root, role, args)
        else:
            handled = _resume_batch(root, role, args)
        if not handled:
            _claim_queued(root, role, args)


def sweep_batch(root, role, batch_id):
    swept = []
    for path in list_mail(root, role, "new"):
        doc = read_item(path)
        if doc.get("batch_id") == batch_id:
            target = inbox_dir(root, role) / "in_process" / path.name
            if target.exists():
                raise MailError([f"claim target already exists: {target}"])
            os.replace(path, target)
            swept.append(target)
    return swept


def _select_done(root, role, args):
    in_process = list_mail(root, role, "in_process")
    if not in_process:
        raise MailError([f"no in-process mail for `{role}`"])
    if not args.id:
        return in_process
    selected = [p for p in in_process if read_item(p).get("id") == args.id]
    if not selected:
        raise MailError([f"mail `{args.id}` is not in process for `{role}`"])
    return selected


def _check_owners(role, selected, args):
    owners = {item_owner(read_item(p)) for p in selected} - {None}
    if len(owners) > 1:
        raise MailError(
            [
                f"`{role}` in-process items have mixed ownership; completion is ambiguous",
                "queue state is owned by the tool; do not repair files by hand",
            ]
        )
    if owners and args.session not in owners:
        owner = next(iter(owners))
        raise MailError(
            [
                f"`{role}` in-process mail is owned by session {owner}; refusing to complete",
                "only the owning session may complete it",
                f"ask the operator; after the operator stops session {owner}, retry pull with takeover: true",
            ]
        )


def _complete_mail(root, role, path, result):
    doc = read_item(path)
    doc["completed_at"] = iso_now()
    if result:
        doc["result"] = result
    write_json_atomic(path, doc)
    target = inbox_dir(root, role) / "completed" / path.name
    if target.exists():
        raise MailError([f"completed target already exists: {target}"])
    os.replace(path, target)
    return target


def cmd_done(args):
    root = args.root
    role = args.role
    ensure_base(root)
    ensure_role(root, role)
    with lock(root, f"role-{role}"):
        selected = _select_done(root, role, args)
        _check_owners(role, selected, args)
        completed = [_complete_mail(root, role, p, args.result) for p in selected]
        waiting = bool(list_mail(root, role, "new"))
    lines = [
        f"COMPLETED: {os.path.relpath(p, str(Path(root).resolve()))}"
        for p in completed
    ]
    lines.append("MAIL_WAITING" if waiting else "NO_TASK")
    emit(
        args,
        "\n".join(lines),
        {
            "command": "done",
            "completed": [
                os.path.relpath(p, str(Path(root).resolve())) for p in completed
            ],
            "mail_waiting": waiting,
        },
    )


def _queued_summary(root, role):
    queued = []
    for path in list_mail(root, role, "new"):
        doc = read_item(path)
        queued.append(
            {
                "id": doc["id"],
                "priority": doc["priority"],
                "from": doc["from"],
                "type": doc["type"],
                "task": doc.get("task"),
            }
        )
    return queued


def _holder_summary(root, role):
    holding = []
    for path in list_mail(root, role, "in_process"):
        doc = read_item(path)
        holding.append(
            {
                "id": doc["id"],
                "owner": doc.get("owner_session"),
                "task": doc.get("task"),
                "batch_id": doc.get("batch_id"),
                "held_since": doc.get("dequeued_at"),
                "held_seconds": age_seconds(doc.get("dequeued_at")),
            }
        )
    return holding


def _role_report(root, role):
    counts = {state: len(list_mail(root, role, state)) for state in STATES}
    return {
        "counts": counts,
        "new": _queued_summary(root, role),
        "in_process": _holder_summary(root, role),
    }


def _status_lines(roles, report):
    lines = []
    for role in roles:
        counts = report[role]["counts"]
        lines.append(f"ROLE: {role}")
        lines.append(f"NEW: {counts['new']}")
        lines.append(f"IN_PROCESS: {counts['in_process']}")
        lines.append(f"COMPLETED: {counts['completed']}")
        for item in report[role]["new"]:
            lines.append(
                f"NEXT: {item['priority']} {item['id']} from {item['from']} "
                f"type {item['type']} task {item['task'] or '-'}"
            )
        for item in report[role]["in_process"]:
            lines.append(
                f"HOLDER: {item['id']} owner {item['owner'] or '-'} "
                f"task {item['task'] or '-'} held {format_age(item['held_seconds'])}"
            )
    return lines


def cmd_status(args):
    root = args.root
    roles = [args.role] if args.role else discover_roles(root)
    report = {role: _role_report(root, role) for role in roles}
    lines = []
    if args.session:
        lines.append(f"SESSION: {args.session}")
    lines.extend(_status_lines(roles, report))
    data = {"command": "status", "roles": report}
    if args.session:
        data["session"] = args.session
    emit(args, "\n".join(lines), data)


def build_parser():
    parser = argparse.ArgumentParser(prog="mailbox")
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--state-root")
    sub = parser.add_subparsers(dest="command", required=True)

    send = sub.add_parser("send")
    send.add_argument("--from", dest="sender", required=True)
    send.add_argument("--to", required=True)
    send.add_argument("--type", dest="mtype", choices=TYPES, default="handoff")
    send.add_argument("--priority", default="50")
    send.add_argument("--task")
    send.add_argument("--message")
    send.add_argument("--session")
    send.add_argument("--json", action="store_true")
    send.set_defaults(func=cmd_send)

    pull = sub.add_parser("pull")
    pull.add_argument("--as", dest="role", required=True)
    pull.add_argument("--mode", choices=("task", "batch"), default="task")
    pull.add_argument("--session")
    pull.add_argument("--takeover", action="store_true")
    pull.add_argument("--json", action="store_true")
    pull.set_defaults(func=cmd_pull)

    done = sub.add_parser("done")
    done.add_argument("--as", dest="role", required=True)
    done.add_argument("--id")
    done.add_argument("--result")
    done.add_argument("--session")
    done.add_argument("--json", action="store_true")
    done.set_defaults(func=cmd_done)

    status = sub.add_parser("status")
    status.add_argument("--role")
    status.add_argument("--session")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv=None):
    return run_cli(
        build_parser,
        MailError,
        "MAIL",
        lambda args: set_state_root(args.state_root),
        argv,
    )


if __name__ == "__main__":
    sys.exit(main())
