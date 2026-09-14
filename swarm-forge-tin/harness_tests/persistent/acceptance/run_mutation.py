#!/usr/bin/env python3
"""Run acceptance mutation for configured features.

Copies each feature into the shared hot area, generates acceptance entry points
once, then drives ``tools/gherkin-mutator`` through the ``mutation_runner``
worker adapter. Each feature's JSON report lands under the artifacts root; the
copied feature, mutants, and generated tests stay disposable under
``hot_tests/mutation``.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ACCEPTANCE = Path(__file__).resolve().parent


class MutationError(Exception):
    """Raised when a mutation run cannot be set up or reported."""


def load_wiring():
    tools_root = Path(__file__).resolve().parents[2].parent / "tools"
    sys.path.insert(0, str(tools_root))
    import wiring

    return wiring


def implementation_hash(generated_dir):
    """Read the generator's hash of the generated acceptance files."""
    metadata_files = sorted((Path(generated_dir) / "metadata").glob("*.json"))
    if not metadata_files:
        raise MutationError(f"no generator metadata under {generated_dir}")
    return json.loads(metadata_files[0].read_text())["implementation_hash"]


def worker_command():
    """The persistent runner adapter command the mutator starts."""
    return f"{sys.executable} {ACCEPTANCE / 'mutation_runner.py'}"


def mutator_command(mutator, feature_copy, feature_dir, generated, level):
    return [
        str(mutator),
        "--feature",
        str(feature_copy),
        "--work-dir",
        str(feature_dir / "work"),
        "--generated-dir",
        str(generated),
        "--runner-worker",
        worker_command(),
        "--level",
        level,
        "--implementation-hash",
        implementation_hash(generated),
        "--json",
    ]


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", action="append", default=None)
    parser.add_argument("--level", choices=["full", "hard", "soft"], default="hard")
    parser.add_argument("--mutator", default=None)
    return parser.parse_args(argv)


def run_feature(
    feature,
    *,
    parser,
    generator_script,
    mutator,
    work_root,
    report_root,
    level="hard",
):
    """Generate entry points for one feature and run its mutations."""
    feature = Path(feature).resolve()
    feature_dir = Path(work_root).resolve() / feature.stem
    feature_copy = feature_dir / "features" / feature.name
    feature_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(feature, feature_copy)

    base_ir = feature_dir / "base" / f"{feature.stem}.json"
    base_ir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(parser), str(feature_copy), str(base_ir)], check=True)

    generated = feature_dir / "generated"
    subprocess.run(
        [sys.executable, str(generator_script), str(base_ir), str(generated)],
        check=True,
    )

    command = mutator_command(mutator, feature_copy, feature_dir, generated, level)
    proc = subprocess.run(command, capture_output=True, text=True)
    report = _read_report(proc)

    report_path = Path(report_root).resolve() / f"{feature.stem}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _read_report(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise MutationError(
            f"mutator produced no JSON report: {error}\n{proc.stderr}"
        ) from error


def _summary_line(stem, summary):
    return (
        f"MUTATION {stem} total={summary.get('Total', 0)}"
        f" killed={summary.get('Killed', 0)}"
        f" survived={summary.get('Survived', 0)}"
        f" errors={summary.get('Errors', 0)}"
    )


def _totals(report):
    summary = report.get("summary", {})
    return summary.get("Survived", 0), summary.get("Errors", 0)


def main(argv=None):
    wiring = load_wiring()
    resolved = wiring.load()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.feature:
        features = [Path(item) for item in args.feature]
    elif resolved.features is not None:
        features = sorted(resolved.features.glob("*.feature"))
    else:
        features = []

    if not features:
        print("run_mutation: no features to mutate")
        return 0

    mutator = (
        Path(args.mutator)
        if args.mutator
        else resolved.pack_root / "tools" / "gherkin-mutator"
    )
    failed = 0
    for feature in features:
        report = run_feature(
            feature,
            parser=resolved.pack_root / "tools" / "gherkin-parser",
            generator_script=ACCEPTANCE / "generator.py",
            mutator=mutator,
            work_root=resolved.hot_tests / "mutation",
            report_root=resolved.artifacts_root / "mutation",
            level=args.level,
        )
        survived, errors = _totals(report)
        print(_summary_line(Path(feature).stem, report.get("summary", {})))
        if survived or errors:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
