#!/usr/bin/env python3
"""Acceptance entrypoint generator for the todo sample project."""

import hashlib
import json
import re
import sys
from pathlib import Path


def safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def metadata_name(feature_path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(feature_path).lower()).strip("-")
    return f"{slug}.json"


def entrypoint_lines(ir: dict, acceptance_root: Path, project_root: Path) -> list[str]:
    lines = [
        f'"""Generated acceptance tests for {ir.get("name", "unknown")} feature."""',
        "",
        "import json",
        "import sys",
        "",
        f"sys.path.insert(0, {str(acceptance_root)!r})",
        f"sys.path.insert(0, {str(project_root)!r})",
        "sys.dont_write_bytecode = True",
        "",
        "from runtime import Runtime",
        "from steps import STEP_HANDLERS",
        "",
        "_BASE_IR = " + json.dumps(ir, indent=4, sort_keys=True),
        "",
        "IR = _BASE_IR",
        "",
        "",
        "def _build_runtime() -> Runtime:",
        '    """Create a runtime with all step handlers registered."""',
        "    rt = Runtime()",
        "    for pattern, handler in STEP_HANDLERS:",
        "        rt.register(pattern, handler)",
        "    return rt",
        "",
        "",
    ]
    for scenario_index, scenario in enumerate(ir["scenarios"]):
        function_base = safe_name(scenario["name"])
        rows = scenario.get("examples", []) or [{}]
        for example_index, example in enumerate(rows, start=1):
            rows_text = "; ".join(f"{key} = {value}" for key, value in sorted(example.items()))
            docstring = f"Scenario: {scenario['name']}"
            if example:
                docstring = f"{docstring} ({rows_text})"
            lines.append(f"def test_{function_base}__example_{example_index}() -> None:")
            lines.append(f'    """{docstring}"""')
            lines.append("    rt = _build_runtime()")
            lines.append(f"    scenario = IR['scenarios'][{scenario_index}]")
            lines.append("    background = IR.get('background', [])")
            lines.append("    rt.run_scenario(scenario, background)")
            lines.append("")
    return lines


def write_metadata(ir: dict, ir_path: str, output: Path, test_file: Path) -> str:
    metadata_dir = output / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    hash_content = test_file.read_text()
    implementation_hash = "sha256:" + hashlib.sha256(hash_content.encode()).hexdigest()
    feature_path = f"{safe_name(ir.get('name', 'unknown'))}.feature"
    metadata = {
        "schema_version": 1,
        "feature_path": feature_path,
        "ir_path": ir_path,
        "implementation_hash": implementation_hash,
        "hash_scope": "generated_files",
        "generated_files": [str(test_file)],
    }
    meta_file = metadata_dir / metadata_name(feature_path)
    meta_file.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Metadata: {meta_file}")
    print(f"Implementation hash: {implementation_hash}")
    return implementation_hash


def generate_entrypoint(ir_path: str, output_dir: str, project_root: str) -> None:
    """Generate a pytest entry point and metadata for one feature IR."""
    ir = json.loads(Path(ir_path).read_text())
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    acceptance_root = Path(__file__).resolve().parent
    test_file = output / f"test_{safe_name(ir.get('name', 'unknown'))}_acceptance.py"
    test_file.write_text(
        "\n".join(entrypoint_lines(ir, acceptance_root, Path(project_root)))
    )
    print(f"Generated {test_file}")
    write_metadata(ir, ir_path, output, test_file)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(f"Usage: {argv[0]} <json-ir> <generated-test-output> <project-root>")
        return 2
    try:
        generate_entrypoint(argv[1], argv[2], argv[3])
    except Exception as error:  # noqa: BLE001 - surface any generation failure
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
