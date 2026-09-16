#!/usr/bin/env python3
"""Run the wired project's acceptance pipeline: parse, dry-check, generate, test.

The project is chosen by the config: pass ``--config <harness.json>`` or set
``SWARM_CONFIG``. The project's authored tests, features, generated entry points,
artifacts, and state all live in the pack's areas, never in the project tree.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_pack(start: Path) -> Path:
    """Walk up from ``start`` to the harness pack (the dir with tools/wiring.py)."""
    for base in (start, *start.parents):
        for candidate in (
            base / "tools" / "wiring.py",
            base / "swarm-forge-tin" / "tools" / "wiring.py",
        ):
            if candidate.is_file():
                return candidate.parent.parent
    raise SystemExit("run_acceptance: cannot locate the harness pack (tools/wiring.py)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_acceptance")
    parser.add_argument("--config", help="path to the wired project's harness.json")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = args.config or os.environ.get("SWARM_CONFIG")
    if not config:
        print(
            "run_acceptance: pass --config <harness.json> or set SWARM_CONFIG",
            file=sys.stderr,
        )
        return 2
    pack = find_pack(HERE)
    sys.path.insert(0, str(pack / "tools"))
    import wiring

    resolved = wiring.load(config=config)
    if resolved.features is None:
        print("run_acceptance: no features root configured", file=sys.stderr)
        return 2
    parser = pack / "tools" / "gherkin-parser"
    dry_checker = pack / "tools" / "ir-dry-checker"
    generator = HERE / "generator.py"
    output = resolved.hot_tests / "acceptance"
    features = sorted(resolved.features.glob("*.feature"))
    if not features:
        print(f"run_acceptance: no features under {resolved.features}")
        return 0
    resolved.artifacts_root.mkdir(parents=True, exist_ok=True)
    for feature in features:
        ir = resolved.artifacts_root / f"{feature.stem}.json"
        dry = resolved.artifacts_root / f"{feature.stem}.dry.json"
        print(f"=== {feature.stem}: parse ===")
        subprocess.run([str(parser), str(feature), str(ir)], check=True)
        print(f"=== {feature.stem}: dry check ===")
        subprocess.run([str(dry_checker), str(ir), str(dry)], check=True)
        print(f"=== {feature.stem}: generate ===")
        subprocess.run(
            [
                sys.executable,
                str(generator),
                str(ir),
                str(output),
                str(resolved.workspace_root),
            ],
            check=True,
        )
    print("=== run generated acceptance tests ===")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.call(
        [sys.executable, "-m", "pytest", str(output), "-q", "-p", "no:cacheprovider"],
        cwd=resolved.hot_tests,
        env=env,
    )


if __name__ == "__main__":
    sys.exit(main())
