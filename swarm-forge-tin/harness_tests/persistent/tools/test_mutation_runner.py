"""Unit and tool tests for the gherkin mutation runner.

``tools/gherkin-mutator`` mutates one example cell in the parser JSON IR and
asks a project runner adapter whether the generated acceptance entry points
notice. These tests pin the generated-test IR override seam, the adapter's
outcome classification and protocol, and the orchestrator that wires the
mutator to ``hot_tests/mutation`` and writes a report under the artifacts root.
"""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import wiring
from support import env_without_swarm

ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
sys.path.insert(0, str(ACCEPTANCE))

import generator  # noqa: E402
import mutation_runner  # noqa: E402
import run_mutation  # noqa: E402

PACK = wiring.PACK_ROOT
PROBE_TEST = """
import json
import os


def test_probe_value():
    with open(os.environ["SWARM_ACCEPTANCE_IR"], encoding="utf-8") as handle:
        ir = json.load(handle)
    assert ir["value"] == "expected"
"""


def write_probe(generated_dir):
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "test_probe.py").write_text(PROBE_TEST)


def write_ir(tmp_path, value):
    path = tmp_path / f"ir-{value}.json"
    path.write_text(json.dumps({"value": value}))
    return path


def probe_job(feature_json, generated_dir):
    return {
        "id": "m1",
        "feature_json": str(feature_json),
        "generated_dir": str(generated_dir),
        "work_dir": str(generated_dir),
    }


def run_generated(test_file, override=None):
    env = env_without_swarm(PYTHONDONTWRITEBYTECODE="1")
    if override is not None:
        env["SWARM_ACCEPTANCE_IR"] = str(override)
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", "-p", "no:cacheprovider"],
        env=env,
        capture_output=True,
        text=True,
    )


# --- outcome classification and worker protocol ------------------------------


def test_classify_maps_pytest_exit_codes():
    assert mutation_runner.classify(0) == "test_success"
    assert mutation_runner.classify(1) == "test_failure"
    assert mutation_runner.classify(2) == "infrastructure_error"
    assert mutation_runner.classify(5) == "infrastructure_error"


def test_run_job_reports_success_when_tests_pass(tmp_path):
    generated = tmp_path / "generated"
    write_probe(generated)
    result = mutation_runner.run_job(
        probe_job(write_ir(tmp_path, "expected"), generated)
    )
    assert result["id"] == "m1"
    assert result["outcome"] == "test_success"
    assert result["error"] == ""
    assert result["duration"] >= 0


def test_run_job_reports_failure_when_a_mutation_is_killed(tmp_path):
    generated = tmp_path / "generated"
    write_probe(generated)
    result = mutation_runner.run_job(probe_job(write_ir(tmp_path, "changed"), generated))
    assert result["outcome"] == "test_failure"


def test_run_job_reports_error_when_no_tests_are_collected(tmp_path):
    generated = tmp_path / "generated"
    generated.mkdir()
    result = mutation_runner.run_job(probe_job(write_ir(tmp_path, "expected"), generated))
    assert result["outcome"] == "infrastructure_error"
    assert result["output"] or result["error"]


def test_run_job_reports_error_when_python_cannot_start(tmp_path):
    generated = tmp_path / "generated"
    write_probe(generated)
    result = mutation_runner.run_job(
        probe_job(write_ir(tmp_path, "expected"), generated),
        python=str(tmp_path / "no-such-python"),
    )
    assert result["outcome"] == "infrastructure_error"
    assert result["error"]


def test_serve_answers_each_job_with_one_protocol_line(tmp_path):
    generated = tmp_path / "generated"
    write_probe(generated)
    request = json.dumps(probe_job(write_ir(tmp_path, "expected"), generated))
    stdout = io.StringIO()
    mutation_runner.serve(io.StringIO(request + "\n"), stdout)
    response = json.loads(stdout.getvalue().strip())
    assert response["id"] == "m1"
    assert response["outcome"] == "test_success"


def test_serve_reports_malformed_json_without_crashing(tmp_path):
    stdout = io.StringIO()
    mutation_runner.serve(io.StringIO("not json\n"), stdout)
    response = json.loads(stdout.getvalue().strip())
    assert response["outcome"] == "infrastructure_error"


# --- generated-test IR override seam -----------------------------------------


def test_generated_tests_reference_the_ir_override(tmp_path):
    ir = {"name": "Override probe", "background": [], "scenarios": []}
    ir_path = tmp_path / "probe.json"
    ir_path.write_text(json.dumps(ir))
    generated = tmp_path / "generated"
    generator.generate_entrypoint(str(ir_path), str(generated))

    source = (generated / "test_override_probe_acceptance.py").read_text()
    assert "SWARM_ACCEPTANCE_IR" in source
    assert "_BASE_IR" in source


def test_generated_test_runs_the_supplied_override_ir(tmp_path):
    base = {
        "name": "Override probe",
        "background": [],
        "scenarios": [
            {
                "name": "probe",
                "steps": [{"keyword": "Then", "text": "an unsupported probe step"}],
                "examples": [{"value": "base"}],
            }
        ],
    }
    override = {
        "name": "Override probe",
        "background": [],
        "scenarios": [
            {"name": "probe", "steps": [], "examples": [{"value": "base"}]}
        ],
    }
    ir_path = tmp_path / "probe.json"
    ir_path.write_text(json.dumps(base))
    generated = tmp_path / "generated"
    generator.generate_entrypoint(str(ir_path), str(generated))
    test_file = generated / "test_override_probe_acceptance.py"
    override_path = tmp_path / "override.json"
    override_path.write_text(json.dumps(override))

    assert run_generated(test_file).returncode != 0
    assert run_generated(test_file, override=override_path).returncode == 0


# --- orchestrator wiring -----------------------------------------------------


FAKE_MUTATOR = '''#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]


def value(flag):
    return args[args.index(flag) + 1]


print(json.dumps({
    "summary": {"Total": 1, "Killed": 1, "Survived": 0, "Errors": 0},
    "results": [],
    "feature_path": value("--feature"),
    "generated_dir": value("--generated-dir"),
    "work_dir": value("--work-dir"),
    "runner_worker": value("--runner-worker"),
    "implementation_hash": value("--implementation-hash"),
}))
'''


@pytest.fixture
def fake_mutator(tmp_path):
    script = tmp_path / "fake_mutator.py"
    script.write_text(FAKE_MUTATOR)
    script.chmod(0o755)
    return script


def test_run_feature_generates_entrypoints_and_writes_a_report(tmp_path, fake_mutator):
    feature = tmp_path / "probe.feature"
    feature.write_text("Feature: Probe\n\n  Scenario: one\n    Given a probe step\n")
    work_root = tmp_path / "hot" / "mutation"
    report_root = tmp_path / "dump" / "mutation"

    report = run_mutation.run_feature(
        feature,
        parser=PACK / "tools" / "gherkin-parser",
        generator_script=ACCEPTANCE / "generator.py",
        mutator=fake_mutator,
        work_root=work_root,
        report_root=report_root,
        level="full",
    )

    assert report["summary"]["Killed"] == 1
    assert Path(report["feature_path"]).is_file()
    assert Path(report["generated_dir"]).is_dir()
    assert report["generated_dir"] == str((work_root / "probe" / "generated").resolve())
    assert "mutation_runner.py" in report["runner_worker"]
    assert report["implementation_hash"].startswith("sha256:")

    written = json.loads((report_root / "probe.json").read_text())
    assert written["summary"]["Killed"] == 1

    test_files = list((work_root / "probe" / "generated").glob("test_*_acceptance.py"))
    assert len(test_files) == 1


def test_main_reports_aggregate_and_forwards_the_exit_code(tmp_path, fake_mutator, monkeypatch):
    feature = tmp_path / "probe.feature"
    feature.write_text("Feature: Probe\n\n  Scenario: one\n    Given a probe step\n")
    config = tmp_path / "harness.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": ".",
                "state_root": "state",
                "artifacts_root": "dump",
                "hot_tests": "hot",
                "features": str(feature),
            }
        )
    )
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    monkeypatch.chdir(tmp_path)
    wiring.clear_cache()

    code = run_mutation.main(
        ["--feature", str(feature), "--mutator", str(fake_mutator)]
    )

    assert code == 0
    assert (tmp_path / "dump" / "mutation" / "probe.json").is_file()
    wiring.clear_cache()


def test_main_returns_nonzero_when_a_mutation_survives(tmp_path, monkeypatch):
    feature = tmp_path / "probe.feature"
    feature.write_text("Feature: Probe\n\n  Scenario: one\n    Given a probe step\n")
    script = tmp_path / "survivor_mutator.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        'print(json.dumps({"summary": {"Total": 1, "Killed": 0,'
        ' "Survived": 1, "Errors": 0}, "results": []}))\n'
    )
    script.chmod(0o755)
    config = tmp_path / "harness.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": ".",
                "state_root": "state",
                "artifacts_root": "dump",
                "hot_tests": "hot",
                "features": str(feature),
            }
        )
    )
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    monkeypatch.chdir(tmp_path)
    wiring.clear_cache()

    code = run_mutation.main(["--feature", str(feature), "--mutator", str(script)])
    assert code == 1
    wiring.clear_cache()


# --- real mutator + worker adapter integration -------------------------------


def test_real_mutator_kills_the_planted_probe(tmp_path):
    feature = tmp_path / "probe.feature"
    feature.write_text(
        "Feature: Mutation probe\n\n"
        "  Scenario Outline: probe\n"
        "    Given the value is <value>\n\n"
        "    Examples:\n"
        "      | value    |\n"
        "      | expected |\n"
    )
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "test_probe.py").write_text(PROBE_TEST)
    command = [
        str(PACK / "tools" / "gherkin-mutator"),
        "--feature",
        str(feature),
        "--work-dir",
        str(tmp_path / "work"),
        "--generated-dir",
        str(generated),
        "--runner-worker",
        run_mutation.worker_command(),
        "--level",
        "full",
        "--implementation-hash",
        "sha256:" + "0" * 64,
        "--json",
    ]

    proc = subprocess.run(command, capture_output=True, text=True)
    report = json.loads(proc.stdout)
    summary = report["summary"]

    assert summary["Total"] >= 1
    assert summary["Errors"] == 0
    assert summary["Killed"] == summary["Total"]
    assert proc.returncode == 0

