"""Unit tests for the deterministic coder payload delivered by ``team_context``.

The payload is the coder's whole assignment: a fixed sequence of 11 sections
assembled from the task record and the resolved harness config. These tests pin
the section shape, the per-section sources, the coder-only trigger, and the
stability that makes a resumed session deterministic.
"""

import datetime
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest
import team
import wiring
from support import env_without_swarm, project_config, run_tool

TEAM = "team.py"

SECTION_HEADERS = [
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
]

ABSENT_ROOTS = {
    "workspace_root": "/absent/project",
    "state_root": "/absent/project/.state",
    "artifacts_root": "/absent/project/dump",
    "hot_tests": "/absent/project/hot",
    "persistent_tests": [
        {"root": "/absent/project/tests", "pythonpath": ["."], "kind": "project"}
    ],
}


@pytest.fixture(autouse=True)
def _clear_wiring_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def task_dir(project, task="c1"):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return project / "state" / "tasks" / today / task


def open_coder(project, config, state_root, task="c1", *extra):
    return run_tool(
        TEAM, project, config, "open", task, "--role", "coder", *extra,
        state_root=state_root,
    )


def bind_worker(project, config, state_root, task="c1", session="sw"):
    return run_tool(
        TEAM, project, config, "bind", task, "--seat", "worker",
        "--session", session, state_root=state_root,
    )


def context(project, config, state_root, session="sw", *extra):
    return run_tool(
        TEAM, project, config, "context", "--session", session, *extra,
        state_root=state_root,
    )


def payload_headers(text):
    known = set(SECTION_HEADERS)
    return [line.strip() for line in text.splitlines() if line.strip() in known]


def payload_section(text, header):
    lines = text.splitlines()
    start = lines.index(header) + 1
    body = []
    for line in lines[start:]:
        if line.strip() in SECTION_HEADERS:
            break
        body.append(line)
    return "\n".join(body)


def absent_config(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = project / "harness.json"
    config.write_text(json.dumps({"version": 1, **ABSENT_ROOTS}))
    return project, config, project / "real-state"


# --- feature scenario 1 and 2: fixed sections in order, exactly 11 ----------


def test_payload_has_the_fixed_sections_in_order_and_exactly_eleven(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_headers(result.stdout) == SECTION_HEADERS
    assert len(payload_headers(result.stdout)) == 11


# --- feature scenario 3: TASK and DEFINITION OF DONE come from task.json -----


@pytest.mark.parametrize(
    "task,done",
    [
        ("feature/periods", "the persistent tests pass"),
        ("bug/leap-year-crash", "a regression test proves the fix"),
    ],
)
def test_task_and_definition_come_from_task_json(tmp_path, task, done):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(
        project, config, state_root, task, "--definition", done
    ).returncode == 0
    assert bind_worker(project, config, state_root, task=task).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert task in payload_section(result.stdout, "TASK")
    assert done in payload_section(result.stdout, "DEFINITION OF DONE")


def test_open_records_definition_from_the_flag(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    result = open_coder(
        project, config, state_root, "c1", "--definition", "the persistent tests pass"
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["definition_of_done"] == "the persistent tests pass"


def test_open_parses_task_and_definition_from_the_brief(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text(
        "## TASK\nImplement strict parsing\n"
        "## DEFINITION OF DONE\n1. tests pass\n2. lint clean\n"
    )
    result = run_tool(
        TEAM, project, config, "open", "c1", "--role", "coder", "--brief", str(brief)
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["task_text"] == "Implement strict parsing"
    assert "tests pass" in doc["definition_of_done"]


def test_open_explicit_flags_win_over_brief_text(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("## TASK\nfrom brief\n## DEFINITION OF DONE\nfrom brief done\n")
    result = run_tool(
        TEAM, project, config, "open", "c1", "--role", "coder", "--brief", str(brief),
        "--task-text", "explicit text", "--definition", "explicit done",
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["task_text"] == "explicit text"
    assert doc["definition_of_done"] == "explicit done"


def test_open_parses_interface_contract_and_files_from_design(tmp_path):
    project, config = project_config(tmp_path)
    design = tmp_path / "design.md"
    design.write_text(
        "## INTERFACE CONTRACT\nfrozen signature\n## FILES\nsrc/a.py\n"
    )
    result = run_tool(
        TEAM, project, config, "open", "c1", "--role", "coder", "--design", str(design)
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["interface_contract"] == "frozen signature"
    assert doc["files"] == "src/a.py"


# --- feature scenario 4: resolved paths come from the config, not the disk ---


@pytest.mark.parametrize(
    "setting,location",
    [
        ("workspace root", "/absent/project"),
        ("state root", "/absent/project/.state"),
        ("artifacts root", "/absent/project/dump"),
        ("hot tests root", "/absent/project/hot"),
        ("persistent test root", "/absent/project/tests"),
    ],
)
def test_resolved_paths_report_configured_absent_locations(
    tmp_path, setting, location
):
    project, config, state_root = absent_config(tmp_path)
    assert not Path(location).exists()
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    body = payload_section(result.stdout, "RESOLVED PATHS")
    assert f"{setting}: {location}" in body


# --- feature scenario 5: stable across calls --------------------------------


def test_payload_is_stable_across_calls(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    first = context(project, config, state_root)
    second = context(project, config, state_root)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout


def test_journal_growth_does_not_appear_in_the_payload(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    first = context(project, config, state_root)
    journal = run_tool(
        TEAM, project, config, "journal", "--session", "sw", "--kind", "plan",
        "--entry", json.dumps({"plan": "journal-sentinel"}),
        state_root=state_root,
    )
    assert journal.returncode == 0, journal.stderr
    again = context(project, config, state_root)

    assert "journal-sentinel" not in again.stdout
    assert again.stdout == first.stdout


# --- section sources ---------------------------------------------------------


def test_feature_section_inlines_the_feature_input(tmp_path):
    project, config = project_config(tmp_path, artifacts_root="artifacts")
    state_root = project / "state"
    feature = tmp_path / "test.feature"
    feature.write_text("Feature: Test\n  Scenario: x\n    Given y\n")
    artifacts = project / "artifacts"
    artifacts.mkdir()
    (artifacts / "test.json").write_text('{"name": "test", "scenarios": []}')
    assert open_coder(
        project, config, state_root, "c1", "--feature", str(feature)
    ).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert "Feature: Test" in payload_section(result.stdout, "FEATURE")


def test_interface_contract_falls_back_to_the_design_input(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    design = tmp_path / "design.md"
    design.write_text("## INTERFACE CONTRACT\nthe design body\n")
    assert open_coder(
        project, config, state_root, "c1", "--design", str(design)
    ).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert "the design body" in payload_section(result.stdout, "INTERFACE CONTRACT")


def test_files_flag_overrides_the_design_fallback(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    design = tmp_path / "design.md"
    design.write_text("## INTERFACE CONTRACT\nthe design body\n")
    assert open_coder(
        project, config, state_root, "c1", "--design", str(design),
        "--files", "src/a.py",
    ).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert payload_section(result.stdout, "FILES") == "src/a.py"


def test_inputs_section_lists_the_copied_input_names(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    brief = tmp_path / "brief.md"
    brief.write_text("## TASK\nthe brief\n")
    assert open_coder(
        project, config, state_root, "c1", "--brief", str(brief)
    ).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert "brief.md" in payload_section(result.stdout, "INPUTS")


def test_prior_attempt_renders_output_artifacts(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0

    fresh = context(project, config, state_root)
    assert "no prior attempt" in payload_section(fresh.stdout, "PRIOR ATTEMPT")

    attempt = run_tool(
        TEAM, project, config, "attempt", "--session", "sw",
        "--command", "python3 -c \"print('prior-sentinel')\"",
        state_root=state_root,
    )
    assert attempt.returncode == 0, attempt.stderr
    after = context(project, config, state_root)
    assert "prior-sentinel" in payload_section(after.stdout, "PRIOR ATTEMPT")


# --- trigger and non-coder / delta behaviour ---------------------------------


def test_non_coder_full_keeps_input_and_journal_delivery(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    brief = tmp_path / "brief.md"
    brief.write_text("the refactorer brief body")
    opened = run_tool(
        TEAM, project, config, "open", "r1", "--role", "refactorer",
        "--brief", str(brief), state_root=state_root,
    )
    assert opened.returncode == 0, opened.stderr
    assert bind_worker(project, config, state_root, task="r1").returncode == 0

    result = run_tool(
        TEAM, project, config, "context", "--session", "sw", state_root=state_root
    )
    assert result.returncode == 0, result.stderr
    assert "CONTEXT: r1 seat worker mode full" in result.stdout
    assert "PACK: brief.md" in result.stdout
    assert "the refactorer brief body" in result.stdout
    assert payload_headers(result.stdout) == []


def test_coder_delta_still_delivers_journal_entries(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_coder(project, config, state_root).returncode == 0
    assert bind_worker(project, config, state_root).returncode == 0
    assert context(project, config, state_root).returncode == 0
    journal = run_tool(
        TEAM, project, config, "journal", "--session", "sw", "--kind", "plan",
        "--entry", json.dumps({"plan": "delta-sentinel"}),
        state_root=state_root,
    )
    assert journal.returncode == 0, journal.stderr

    delta = run_tool(
        TEAM, project, config, "context", "--session", "sw", "--delta",
        state_root=state_root,
    )
    assert delta.returncode == 0, delta.stderr
    assert "mode delta" in delta.stdout
    assert "delta-sentinel" in delta.stdout


# --- pure helpers ------------------------------------------------------------


def test_persistent_test_root_prefers_the_project_entry():
    resolved = types.SimpleNamespace(
        persistent_tests=(
            {"root": Path("/harness"), "kind": "harness"},
            {"root": Path("/project"), "kind": "project"},
        )
    )
    assert team.persistent_test_root(resolved) == Path("/project")


def test_persistent_test_root_falls_back_and_handles_absence():
    only = types.SimpleNamespace(
        persistent_tests=({"root": Path("/harness"), "kind": "harness"},)
    )
    assert team.persistent_test_root(only) == Path("/harness")
    empty = types.SimpleNamespace(persistent_tests=())
    assert team.persistent_test_root(empty) is None


def test_persistent_test_root_prefers_harness_for_self_hosted_pack():
    resolved = types.SimpleNamespace(
        config_path=Path("/pack/harness.json"),
        pack_root=Path("/pack"),
        persistent_tests=(
            {"root": Path("/pack/project"), "kind": "project"},
            {"root": Path("/pack/harness"), "kind": "harness"},
        ),
    )
    assert team.persistent_test_root(resolved) == Path("/pack/harness")


def run_self_hosted_tool(state_root, *args):
    """Run team.py against the pack's own config with state kept off the tree."""
    workspace = wiring.PACK_ROOT.parent
    return subprocess.run(
        [
            sys.executable,
            str(wiring.PACK_ROOT / "tools" / "team.py"),
            "--root",
            str(workspace),
            "--state-root",
            str(state_root),
            *args,
        ],
        env=env_without_swarm(),
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )


def test_self_hosted_coder_payload_names_the_harness_persistent_root(tmp_path):
    """A coder task in the pack's own workspace resolves the harness test root."""
    state_root = tmp_path / "selfhost-state"
    opened = run_self_hosted_tool(state_root, "open", "selfhost", "--role", "coder")
    assert opened.returncode == 0, opened.stderr
    bound = run_self_hosted_tool(
        state_root, "bind", "selfhost", "--seat", "worker", "--session", "sw-self"
    )
    assert bound.returncode == 0, bound.stderr

    result = run_self_hosted_tool(state_root, "context", "--session", "sw-self")
    assert result.returncode == 0, result.stderr
    expected = wiring.PACK_ROOT / "harness_tests" / "persistent"
    assert f"persistent test root: {expected}" in payload_section(
        result.stdout, "RESOLVED PATHS"
    )
    assert f"cd {expected} " in payload_section(result.stdout, "HOW TO RUN")


def test_extract_section_reads_markdown_and_bold_headers():
    assert team.extract_section("## TASK\nDo it\n## NEXT\nx", "TASK") == "Do it"
    assert team.extract_section("**TASK**\nDo it", "TASK") == "Do it"
    assert team.extract_section("plain text", "TASK") is None


def test_section_header_normalizes_markdown_bold_and_plain_headers():
    assert team._section_header("") is None
    assert team._section_header("## TASK") == "TASK"
    assert team._section_header("**TASK**") == "TASK"
    assert team._section_header("TASK (details)") == "TASK"
    assert team._section_header("lowercase") is None
    assert team._section_header("123") is None


def test_feature_lines_handles_absent_empty_and_non_feature_dirs(tmp_path):
    assert team._feature_lines(tmp_path / "missing") == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert team._feature_lines(empty) == []
    (empty / "notes.txt").write_text("not a feature")
    assert team._feature_lines(empty) == []


def test_feature_lines_reads_the_first_feature_file(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "a.feature").write_text("Feature: A\n  Scenario: one\n")
    assert team._feature_lines(input_dir) == ["Feature: A", "  Scenario: one"]


def test_feature_lines_tolerates_an_unreadable_feature_file(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "bad.feature").write_bytes(b"\xff\xfe")
    assert team._feature_lines(input_dir) == []


def test_read_input_reads_or_reports_absence(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "design.md").write_text("body")
    assert team._read_input(input_dir, "design.md") == "body"
    assert team._read_input(input_dir, "missing.md") is None
    assert team._read_input(input_dir, None) is None
    (input_dir / "bad.md").write_bytes(b"\xff\xfe")
    assert team._read_input(input_dir, "bad.md") is None


def test_prior_attempt_lines_reports_no_attempt_and_renders_files(tmp_path):
    output = tmp_path / "output"
    assert team._prior_attempt_lines(output) == [team.NO_PRIOR_ATTEMPT]
    output.mkdir()
    (output / "attempt-01.txt").write_text("first run\nsecond line")
    (output / "attempt-02.txt").write_bytes(b"\xff\xfe")
    assert team._prior_attempt_lines(output) == [
        "--- attempt-01.txt ---",
        "first run",
        "second line",
        "--- attempt-02.txt ---",
        "<unreadable: attempt-02.txt>",
    ]
