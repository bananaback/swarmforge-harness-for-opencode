"""Step handlers for the acceptance pipeline acceptance feature.

The handlers drive the vendored ``gherkin-parser``/``ir-dry-checker`` and the
project entrypoint generator/mutation runner exactly as the pipeline does; the
feature pins the tool contracts, so the handlers only build fixtures, invoke the
tools, and read back their reports.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from runtime import World

from .common import TOOLS, _temp_root, step_values

ACCEPTANCE = Path(__file__).resolve().parents[1]
PARSER = TOOLS / "gherkin-parser"
DRY_CHECKER = TOOLS / "ir-dry-checker"
GENERATOR = ACCEPTANCE / "generator.py"
MUTATOR = TOOLS / "gherkin-mutator"


def _write_feature(world: World, text: str) -> None:
    path = _temp_root() / "sample.feature"
    path.write_text(text)
    world.state["feature_path"] = path


def _write_ir(world: World, ir: dict) -> None:
    path = _temp_root() / "ir.json"
    path.write_text(json.dumps(ir))
    world.state["ir_path"] = path


def _parse(world: World) -> None:
    feature = world.state["feature_path"]
    ir_path = _temp_root() / f"{feature.stem}.json"
    proc = subprocess.run(
        [str(PARSER), str(feature), str(ir_path)],
        capture_output=True,
        text=True,
    )
    world.state["parser_exit"] = proc.returncode
    world.state["parser_stderr"] = proc.stderr
    if proc.returncode == 0:
        world.state["parsed_ir"] = json.loads(ir_path.read_text())


# --- parser fixtures and assertions ----------------------------------------


def _feature_with_step(world: World, examples: dict[str, str]) -> None:
    name, scenario, step = step_values(
        examples,
        r'^a feature file named "([^"]*)" with a scenario "([^"]*)" and the '
        r'step "([^"]*)"$',
    )
    _write_feature(
        world,
        f"Feature: {name}\n  Scenario: {scenario}\n    Given {step}\n",
    )


def _feature_without_declaration(world: World, examples: dict[str, str]) -> None:
    (line,) = step_values(
        examples,
        r'^a feature file that declares no feature and contains "([^"]*)"$',
    )
    _write_feature(world, f"{line}\n")


def _orphan_examples(world: World, examples: dict[str, str]) -> None:
    _write_feature(
        world,
        "Feature: Orphan\n"
        "  Examples:\n"
        "    | a |\n"
        "    | 1 |\n",
    )


def _ragged_examples(world: World, examples: dict[str, str]) -> None:
    row_cells, header_cells = step_values(
        examples,
        r"^a feature file whose example row has (.+?) cells and whose header "
        r"has (.+?) cells$",
    )
    header = " | ".join(f"h{index}" for index in range(int(header_cells)))
    row = " | ".join(f"v{index}" for index in range(int(row_cells)))
    _write_feature(
        world,
        "Feature: Ragged\n"
        "  Scenario Outline: Ragged\n"
        "    Given a value\n"
        "    Examples:\n"
        f"      | {header} |\n"
        f"      | {row} |\n",
    )


def _parser_runs(world: World, examples: dict[str, str]) -> None:
    _parse(world)


def _parser_exits_with(world: World, examples: dict[str, str]) -> None:
    (exit_code,) = step_values(
        examples, r"^the acceptance parser exits with code (.+)$"
    )
    assert world.state["parser_exit"] == int(exit_code), world.state.get(
        "parser_stderr"
    )


def _parsed_name(world: World, examples: dict[str, str]) -> None:
    (name,) = step_values(examples, r'^the parsed feature is named "([^"]*)"$')
    assert world.state["parsed_ir"]["name"] == name


def _parsed_scenario(world: World, examples: dict[str, str]) -> None:
    (scenario,) = step_values(
        examples, r'^the parsed scenario is named "([^"]*)"$'
    )
    assert world.state["parsed_ir"]["scenarios"][0]["name"] == scenario


def _parsed_step(world: World, examples: dict[str, str]) -> None:
    step, parameter = step_values(
        examples,
        r'^the parsed step is "([^"]*)" with parameter "([^"]*)"$',
    )
    parsed = world.state["parsed_ir"]["scenarios"][0]["steps"][0]
    assert parsed["text"] == step, f"{parsed['text']!r} != {step!r}"
    assert parsed.get("parameters", []) == [parameter], parsed.get("parameters")


# --- dry checker -----------------------------------------------------------


def _ir_repeating_step(world: World, examples: dict[str, str]) -> None:
    step, scenarios = step_values(
        examples,
        r'^a parsed IR that repeats the step "([^"]*)" in (.+) scenarios$',
    )
    _write_ir(
        world,
        {
            "name": "Repeated",
            "scenarios": [
                {
                    "name": f"Scenario {index}",
                    "steps": [
                        {"keyword": "Given", "text": step},
                        {"keyword": "Given", "text": step},
                    ],
                    "examples": [],
                }
                for index in range(int(scenarios))
            ],
        },
    )


def _ir_with_two_steps(world: World, examples: dict[str, str]) -> None:
    first, second = step_values(
        examples,
        r'^a parsed IR whose scenario holds the steps "([^"]*)" and '
        r'"([^"]*)"$',
    )
    _write_ir(
        world,
        {
            "name": "Variant",
            "scenarios": [
                {
                    "name": "Scenario",
                    "steps": [
                        {"keyword": "Given", "text": first},
                        {"keyword": "Given", "text": second},
                    ],
                    "examples": [],
                }
            ],
        },
    )


def _dry_checker_runs(world: World, examples: dict[str, str]) -> None:
    (mode,) = step_values(examples, r"^the dry checker runs(?: (.+))?$")
    report_path = _temp_root() / "dry.json"
    command = [str(DRY_CHECKER)]
    if mode == "with --include-exact":
        command.append("--include-exact")
    command += [str(world.state["ir_path"]), str(report_path)]
    proc = subprocess.run(command, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    world.state["dry_report"] = json.loads(report_path.read_text())


def _finding_kinds(world: World) -> set[str]:
    """Return the set of finding kinds in the current dry report."""
    return {finding["kind"] for finding in world.state["dry_report"]["findings"]}


def _dry_report_finding(world: World, examples: dict[str, str]) -> None:
    outcome, kind = step_values(
        examples, r'^the dry report (.+?) a "([^"]*)" finding$'
    )
    kinds = _finding_kinds(world)
    if outcome == "reports":
        assert kind in kinds, f"{kind!r} not among {sorted(kinds)}"
    elif outcome == "does not report":
        assert kind not in kinds, f"{kind!r} unexpectedly among {sorted(kinds)}"
    else:
        raise AssertionError(f"unknown dry outcome: {outcome}")


def _dry_report_kinds(world: World, examples: dict[str, str]) -> None:
    (kinds,) = step_values(
        examples, r'^the dry report contains only the "([^"]*)" kinds$'
    )
    expected = {kind.strip() for kind in kinds.split(",") if kind.strip()}
    actual = _finding_kinds(world)
    assert actual == expected, f"dry report kinds {sorted(actual)} != {sorted(expected)}"


# --- generator -------------------------------------------------------------


def _ir_with_example_rows(world: World, examples: dict[str, str]) -> None:
    (count,) = step_values(
        examples, r"^a parsed IR whose scenario has (.+) example rows$"
    )
    _write_ir(
        world,
        {
            "name": "Generated",
            "scenarios": [
                {
                    "name": "Scenario",
                    "steps": [{"keyword": "Given", "text": "the value is <v>"}],
                    "examples": [
                        {"v": str(index)} for index in range(int(count))
                    ],
                }
            ],
        },
    )


def _generator_runs(world: World, examples: dict[str, str]) -> None:
    output = _temp_root() / "generated"
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), str(world.state["ir_path"]), str(output)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    generated = sorted(output.glob("test_*.py"))
    assert generated, f"no generated entry point under {output}"
    text = generated[0].read_text()
    world.state["generated_tests"] = len(re.findall(r"^def test_", text, re.M))


def _generated_test_count(world: World, examples: dict[str, str]) -> None:
    (tests,) = step_values(
        examples, r"^the generated entry point declares (.+) test functions$"
    )
    assert world.state["generated_tests"] == int(tests)


# --- mutator ---------------------------------------------------------------


def _tiny_feature(world: World, examples: dict[str, str]) -> None:
    _write_feature(
        world,
        "Feature: Tiny\n"
        "  Scenario Outline: Tiny\n"
        '    When the durable store CLI refuses with the problems "x"\n'
        "    Then the durable store CLI exits with code <exit_code>\n"
        "    Examples:\n"
        "      | exit_code |\n"
        "      | 2         |\n",
    )


def _mutator_runs(world: World, examples: dict[str, str]) -> None:
    (level,) = step_values(examples, r'^the mutator runs at level "([^"]*)"$')
    import run_mutation

    report = run_mutation.run_feature(
        world.state["feature_path"],
        parser=PARSER,
        generator_script=GENERATOR,
        mutator=MUTATOR,
        work_root=_temp_root() / "mutation-work",
        report_root=_temp_root() / "mutation-report",
        level=level,
    )
    world.state["mutation_report"] = report


def _mutation_summary(world: World, examples: dict[str, str]) -> None:
    killed, survived = step_values(
        examples,
        r"^the mutation report has (.+) killed and (.+) surviving mutants$",
    )
    summary = world.state["mutation_report"]["summary"]
    assert summary["Killed"] == int(killed), summary
    assert summary["Survived"] == int(survived), summary


HANDLERS = [
    (
        r'^a feature file named "([^"]*)" with a scenario "([^"]*)" and the '
        r'step "([^"]*)"$',
        _feature_with_step,
    ),
    (
        r'^a feature file that declares no feature and contains "([^"]*)"$',
        _feature_without_declaration,
    ),
    (r"^a feature file with an examples table outside any scenario$", _orphan_examples),
    (
        r"^a feature file whose example row has (.+?) cells and whose header "
        r"has (.+?) cells$",
        _ragged_examples,
    ),
    (r"^the acceptance parser parses it$", _parser_runs),
    (r"^the acceptance parser exits with code (.+)$", _parser_exits_with),
    (r'^the parsed feature is named "([^"]*)"$', _parsed_name),
    (r'^the parsed scenario is named "([^"]*)"$', _parsed_scenario),
    (
        r'^the parsed step is "([^"]*)" with parameter "([^"]*)"$',
        _parsed_step,
    ),
    (
        r'^a parsed IR that repeats the step "([^"]*)" in (.+) scenarios$',
        _ir_repeating_step,
    ),
    (
        r'^a parsed IR whose scenario holds the steps "([^"]*)" and "([^"]*)"$',
        _ir_with_two_steps,
    ),
    (r"^the dry checker runs(?: (.+))?$", _dry_checker_runs),
    (r'^the dry report (.+?) a "([^"]*)" finding$', _dry_report_finding),
    (r'^the dry report contains only the "([^"]*)" kinds$', _dry_report_kinds),
    (
        r"^a parsed IR whose scenario has (.+) example rows$",
        _ir_with_example_rows,
    ),
    (r"^the acceptance generator generates entry points$", _generator_runs),
    (
        r"^the generated entry point declares (.+) test functions$",
        _generated_test_count,
    ),
    (r"^a tiny feature whose single example value is asserted$", _tiny_feature),
    (r'^the mutator runs at level "([^"]*)"$', _mutator_runs),
    (
        r"^the mutation report has (.+) killed and (.+) surviving mutants$",
        _mutation_summary,
    ),
]
