#!/usr/bin/env python3
"""wiring -- resolve harness paths from harness.json, environment, or defaults."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "harness.json"
DEFAULT_ROLES = (
    "orchestrator",
    "specifier",
    "coder",
    "refactorer",
    "architect",
    "mentor",
)
_CACHE = {}


class WiringError(Exception):
    """Raised when a config is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class Wiring:
    pack_root: Path
    workspace_root: Path
    state_root: Path
    artifacts_root: Path
    hot_tests: Path
    persistent_tests: tuple
    source_roots: tuple
    features: Path | None
    roles: tuple
    config_path: Path | None

    def as_dict(self):
        return {
            "pack_root": str(self.pack_root),
            "workspace_root": str(self.workspace_root),
            "state_root": str(self.state_root),
            "artifacts_root": str(self.artifacts_root),
            "hot_tests": str(self.hot_tests),
            "persistent_tests": [
                {
                    "root": str(entry["root"]),
                    "pythonpath": [str(path) for path in entry["pythonpath"]],
                    "kind": entry["kind"],
                }
                for entry in self.persistent_tests
            ],
            "source_roots": [str(path) for path in self.source_roots],
            "features": str(self.features) if self.features else None,
            "roles": list(self.roles),
            "config_path": str(self.config_path) if self.config_path else None,
        }


def clear_cache():
    _CACHE.clear()


def _expand(value, base):
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(data, base, key, env_name, default):
    if env_name:
        override = os.environ.get(env_name)
        if override:
            return _expand(override, Path.cwd())
    if key in data:
        return _expand(data[key], base)
    return default


def _resolve_pack(config_path, data):
    if config_path and (config_path.parent / "tools" / "wiring.py").is_file():
        pack = config_path.parent
    else:
        pack = PACK_ROOT
    override = os.environ.get("SWARM_PACK")
    if override:
        pack = _expand(override, Path.cwd())
    return pack


def _resolve_workspace(data, base, pack):
    return _resolve_path(data, base, "workspace_root", "SWARM_WORKSPACE", pack.parent)


def _resolve_state(data, base, workspace):
    return _resolve_path(
        data,
        base,
        "state_root",
        "SWARM_STATE_ROOT",
        workspace / "swarm-forge-tin" / ".swarmforge",
    )


def _resolve_artifacts(data, base, pack):
    return _resolve_path(data, base, "artifacts_root", None, pack / "dump")


def _resolve_hot(data, base, pack):
    return _resolve_path(data, base, "hot_tests", "SWARM_HOT", pack / "hot_tests")


def _config_candidates(start):
    if start is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start).expanduser().resolve()
    if start_path.is_file():
        start_path = start_path.parent
    candidates = []
    for directory in (start_path, *start_path.parents):
        for candidate in (
            directory / CONFIG_NAME,
            directory / "swarm-forge-tin" / CONFIG_NAME,
        ):
            if candidate.is_file() and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def find_config(start=None):
    override = os.environ.get("SWARM_CONFIG")
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise WiringError(f"SWARM_CONFIG points to a missing file: {path}")
        return path.resolve()
    for candidate in _config_candidates(start):
        return candidate
    pack_override = os.environ.get("SWARM_PACK")
    if pack_override:
        candidate = _expand(pack_override, Path.cwd()) / CONFIG_NAME
        if candidate.is_file():
            return candidate
    if (PACK_ROOT / CONFIG_NAME).is_file():
        return PACK_ROOT / CONFIG_NAME
    global_config = Path.home() / ".config" / "swarm-forge" / CONFIG_NAME
    if global_config.is_file():
        return global_config
    return None


def _read_config(config_path):
    if config_path is None:
        return {}
    try:
        data = json.loads(config_path.read_text())
    except OSError as error:
        raise WiringError(f"cannot read config {config_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise WiringError(f"invalid JSON in {config_path}: {error}") from error
    if not isinstance(data, dict):
        raise WiringError(f"config {config_path} must be a JSON object")
    return data


def _resolve_persistent(entries, base):
    resolved = []
    for entry in entries:
        if not isinstance(entry, dict) or "root" not in entry:
            raise WiringError("persistent_tests entries need a root")
        root = _expand(entry["root"], base)
        pythonpath = tuple(
            _expand(item, root) for item in entry.get("pythonpath", [])
        )
        resolved.append(
            {
                "root": root,
                "pythonpath": pythonpath,
                "kind": entry.get("kind", "test"),
            }
        )
    return tuple(resolved)


def load(config=None, start=None):
    key = (
        str(config) if config else "",
        str(Path(start).resolve()) if start else "",
        os.environ.get("SWARM_CONFIG", ""),
        os.environ.get("SWARM_PACK", ""),
        os.environ.get("SWARM_WORKSPACE", ""),
        os.environ.get("SWARM_STATE_ROOT", ""),
        os.environ.get("SWARM_HOT", ""),
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    config_path = Path(config).expanduser().resolve() if config else find_config(start)
    data = _read_config(config_path)
    base = config_path.parent if config_path else PACK_ROOT
    pack = _resolve_pack(config_path, data)
    workspace = _resolve_workspace(data, base, pack)
    state = _resolve_state(data, base, workspace)
    artifacts = _resolve_artifacts(data, base, pack)
    hot = _resolve_hot(data, base, pack)
    persistent = _resolve_persistent(data.get("persistent_tests", []), base)
    source_roots = tuple(
        _expand(item, base) for item in data.get("source_roots", ["src"])
    )
    features = _expand(data["features"], base) if data.get("features") else None
    roles = tuple(data.get("roles", DEFAULT_ROLES))
    result = Wiring(
        pack,
        workspace,
        state,
        artifacts,
        hot,
        persistent,
        source_roots,
        features,
        roles,
        config_path,
    )
    _CACHE[key] = result
    return result


def state_root_for(workspace, override=None):
    if override:
        return _expand(override, Path.cwd())
    env = os.environ.get("SWARM_STATE_ROOT")
    if env:
        return _expand(env, Path.cwd())
    return load(start=workspace).state_root
