#!/usr/bin/env python3
"""Durable JSON state primitives shared by the harness tools.

The mail tool and the team tool both keep append-and-claim state on disk:
advisory locks, atomic JSON writes, JSON listing, and monotonic sequence
allocation. This module owns those primitives once so each tool depends on
the same storage boundary instead of carrying its own copy.
"""

import fcntl
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def lock(lock_dir, name):
    """Hold an exclusive advisory lock at ``lock_dir/<name>.lock``."""
    lock_dir = Path(lock_dir)
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{name}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def write_json_atomic(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(doc, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path):
    with open(path) as handle:
        return json.load(handle)


def list_json(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.name.endswith(".json") and not p.name.startswith(".")
    )


def next_seq(path):
    """Increment and return the counter stored at ``path``."""
    path = Path(path)
    try:
        value = int(path.read_text().strip() or "0")
    except (FileNotFoundError, ValueError):
        value = 0
    value += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n")
    return value


def run_cli(build_parser, error_type, error_label, setup=None, argv=None):
    """Parse argv, resolve --root, dispatch, and render tool errors."""
    args = build_parser().parse_args(argv)
    args.root = str(Path(args.root).resolve())
    if setup is not None:
        setup(args)
    try:
        args.func(args)
    except error_type as error:
        print(f"{error_label} ERROR:", file=sys.stderr)
        for problem in error.problems:
            print(f"- {problem}", file=sys.stderr)
        return 2
    return 0
