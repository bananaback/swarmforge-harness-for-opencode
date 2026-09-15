"""Behavioral contract tests for the task-breaker bridge (tools/taskbreak.py).

The task-breaker agent emits a chunk plan. This bridge turns each plan entry into
a ``team open`` seed, so the tests pin two things: the plan validation, and the
plan -> team_open wiring -- a plan's brief, design, feature, and oracle reach the
opened chunk with no hand translation.

Most cases call ``taskbreak.main`` in-process so coverage and CRAP measure the
bridge itself; one subprocess case pins the CLI contract.
"""

import datetime
import json

import pytest
import taskbreak
import team
import wiring
from support import project_config, run_tool

TOOL = "taskbreak.py"


@pytest.fixture(autouse=True)
def _clear_wiring_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def run_taskbreak(project, *args):
    return taskbreak.main(["--root", str(project), *args])


def task_dir(project, task):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return project / "state" / "tasks" / today / task


def seed_project(tmp_path):
    project, config = project_config(
        tmp_path, artifacts_root="artifacts", source_roots=["src"]
    )
    (project / "features").mkdir()
    feature = project / "features" / "cart.feature"
    feature.write_text("Feature: Cart\n  Scenario: total\n")
    artifacts = project / "artifacts"
    artifacts.mkdir()
    (artifacts / "cart.json").write_text('{"name": "cart", "scenarios": []}')
    return project, config, feature


def chunk(task="cart-domain", role="coder", **overrides):
    entry = {
        "task": task,
        "role": role,
        "brief_text": "TASK\nBuild Cart.\n\nDEFINITION OF DONE\n- [ ] total",
        "design_text": "INTERFACE CONTRACT\nclass Cart: ...\n\nFILES\n- src/cart.py -- Cart",
        "oracle": "pytest unit/test_cart.py -q",
        "goal": "cart total green",
        "rules": "one job per method",
    }
    entry.update(overrides)
    return entry


def write_plan(project, chunks, feature="features/cart.feature", name="plan.json"):
    plan = {"version": 1, "feature": feature, "chunks": chunks}
    path = project / name
    path.write_text(json.dumps(plan))
    return path


# --- role registration ------------------------------------------------------


def test_design_roles_are_registered():
    expected = {"designer", "task-breaker"}
    assert expected <= set(team.ROLES)
    assert expected <= set(wiring.DEFAULT_ROLES)


# --- validation and pure helpers (in-process) -------------------------------


def test_plan_validation_requires_chunks_and_version():
    assert taskbreak.plan_problems({"version": 1}) == [
        "plan requires a non-empty `chunks` list"
    ]
    assert taskbreak.plan_problems({"version": 2, "chunks": [chunk()]}) == [
        "plan version must be 1"
    ]


def test_plan_validation_reports_role_task_and_brief_problems():
    problems = taskbreak.plan_problems(
        {
            "version": 1,
            "chunks": [
                chunk(task="dup", role="designer"),
                chunk(task="dup"),
                "not-an-object",
                {"task": "no-brief", "role": "coder"},
            ],
        }
    )
    text = "\n".join(problems)
    assert "role must be one of: coder, refactorer, architect" in text
    assert "task `dup` is duplicated" in text
    assert "chunk 3 must be an object" in text
    assert "requires `brief_text` or `brief`" in text


def test_with_oracle_appends_once():
    assert taskbreak.with_oracle("TASK\nx", "run it").endswith("ORACLE\nrun it\n")
    already = "TASK\nx\n\nORACLE\nold"
    assert taskbreak.with_oracle(already, "run it") == already
    assert taskbreak.with_oracle("TASK", None) == "TASK"


def test_input_problems_reports_missing_files(tmp_path):
    project, _, _ = seed_project(tmp_path)
    plan = {
        "feature": "features/gone.feature",
        "chunks": [
            chunk(brief="missing.brief.md"),
            chunk(task="c2", design="missing.design.md"),
            chunk(task="c3", feature="features/also-gone.feature"),
            "not-an-object",
        ],
    }
    text = "\n".join(taskbreak.input_problems(plan, str(project)))
    assert "feature not found: features/gone.feature" in text
    assert "chunk 1 brief not found: missing.brief.md" in text
    assert "chunk 2 design not found: missing.design.md" in text
    assert "chunk 3 feature not found: features/also-gone.feature" in text


# --- plan -> team_open wiring ----------------------------------------------


def test_plan_opens_one_chunk_per_entry(tmp_path):
    project, _, _ = seed_project(tmp_path)
    plan = write_plan(
        project,
        [
            chunk(),
            chunk(task="cart-repo", role="refactorer", design_text=None, oracle=None),
        ],
    )
    assert run_taskbreak(project, "--plan", str(plan)) == 0

    doc = json.loads((task_dir(project, "cart-domain") / "task.json").read_text())
    assert doc["role"] == "coder"
    assert doc["definition_of_done"] == "- [ ] total"
    assert doc["interface_contract"] == "class Cart: ..."
    assert doc["files"] == "- src/cart.py -- Cart"
    assert doc["mentor"]["goal"] == "cart total green"
    assert doc["mentor"]["rules"] == "one job per method"

    inputs = task_dir(project, "cart-domain") / "01-coder" / "input"
    brief = (inputs / "01-cart-domain.brief.md").read_text()
    assert "ORACLE\npytest unit/test_cart.py -q" in brief
    assert (inputs / "01-cart-domain.design.md").is_file()
    assert (inputs / "cart.feature").is_file()
    assert (inputs / "cart.json").is_file()

    repo_doc = json.loads((task_dir(project, "cart-repo") / "task.json").read_text())
    assert repo_doc["role"] == "refactorer"


def test_chunk_feature_overrides_the_plan(tmp_path):
    project, _, _ = seed_project(tmp_path)
    (project / "features" / "other.feature").write_text("Feature: Other\n")
    plan = write_plan(
        project,
        [chunk(feature="features/other.feature")],
        feature="features/cart.feature",
    )
    assert run_taskbreak(project, "--plan", str(plan)) == 0
    inputs = task_dir(project, "cart-domain") / "01-coder" / "input"
    assert (inputs / "other.feature").is_file()
    assert not (inputs / "cart.feature").exists()


def test_plan_reports_every_missing_input_and_opens_nothing(tmp_path):
    project, _, _ = seed_project(tmp_path)
    plan = write_plan(
        project,
        [chunk(feature="features/missing.feature")],
        feature="features/also-missing.feature",
    )
    assert run_taskbreak(project, "--plan", str(plan)) == 2
    assert not (project / "state").exists()


def test_duplicate_chunk_task_is_refused(tmp_path):
    project, _, _ = seed_project(tmp_path)
    plan = write_plan(project, [chunk(), chunk()])
    assert run_taskbreak(project, "--plan", str(plan)) == 2


def test_brief_file_reference_is_read_from_workspace(tmp_path):
    project, _, _ = seed_project(tmp_path)
    (project / "chunk.brief.md").write_text(
        "TASK\nFrom a file.\n\nDEFINITION OF DONE\n- [ ] x"
    )
    plan = write_plan(
        project,
        [chunk(task="file-chunk", brief_text=None, brief="chunk.brief.md")],
        feature=None,
    )
    assert run_taskbreak(project, "--plan", str(plan)) == 0
    doc = json.loads((task_dir(project, "file-chunk") / "task.json").read_text())
    assert doc["task_text"] == "From a file."


def test_dry_run_stages_inputs_without_opening(tmp_path, capsys):
    project, _, _ = seed_project(tmp_path)
    plan = write_plan(project, [chunk()], name="cart.plan.json")
    assert run_taskbreak(project, "--plan", str(plan), "--dry-run", "--json") == 0
    assert json.loads(capsys.readouterr().out)["opened"] == ["cart-domain"]
    assert not task_dir(project, "cart-domain").exists()
    staged = project / "artifacts" / "taskbreak" / "cart.plan"
    assert (staged / "01-cart-domain.brief.md").is_file()


def test_invalid_plan_json_is_refused(tmp_path):
    project, _, _ = seed_project(tmp_path)
    plan = project / "plan.json"
    plan.write_text("{not json")
    assert run_taskbreak(project, "--plan", str(plan)) == 2


def test_cli_contract_subprocess(tmp_path):
    project, config, _ = seed_project(tmp_path)
    plan = write_plan(project, [chunk()])
    result = run_tool(TOOL, project, config, "--plan", str(plan), "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["opened"] == ["cart-domain"]
