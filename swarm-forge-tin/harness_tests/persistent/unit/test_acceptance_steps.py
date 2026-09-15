"""Contract tests for the split acceptance step handler registry.

The handlers are grouped into focused modules under ``acceptance/steps``. These
tests guard the aggregation (every feature step resolves to exactly one handler,
and no pattern is registered twice) and pin the mail step helpers the new
features lean on.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import wiring

ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
sys.path.insert(0, str(ACCEPTANCE))

import steps  # noqa: E402
from runtime import World  # noqa: E402
from steps import (  # noqa: E402
    acceptance_pipeline_steps,
    common,
    durable_store_steps,
    harness_cli_steps,
    mail_steps,
    taskbreak_steps,
    team_open_steps,
    team_steps,
    ts_wiring_steps,
    wiring_steps,
)

FEATURES = wiring.PACK_ROOT / "harness_tests" / "persistent" / "features"
PARSER = wiring.PACK_ROOT / "tools" / "gherkin-parser"


def _parse(feature: Path, tmp_path: Path) -> dict:
    ir_path = tmp_path / f"{feature.stem}.json"
    subprocess.run(
        [str(PARSER), str(feature), str(ir_path)], check=True, capture_output=True
    )
    return json.loads(ir_path.read_text())


def _step_texts(ir: dict):
    for step in ir.get("background", []):
        yield step["text"]
    for scenario in ir["scenarios"]:
        for step in scenario["steps"]:
            yield step["text"]


def _matching_patterns(step_text: str) -> list[str]:
    return [
        pattern
        for pattern, _handler in steps.STEP_HANDLERS
        if re.search(pattern, step_text)
    ]


def test_every_mail_step_resolves_to_exactly_one_handler(tmp_path):
    features = sorted(FEATURES.glob("mail_*.feature"))
    assert features, f"no mail features under {FEATURES}"
    for feature in features:
        for step_text in _step_texts(_parse(feature, tmp_path)):
            matches = _matching_patterns(step_text)
            assert len(matches) == 1, (
                f"{step_text!r} in {feature.name} matched {len(matches)} handlers"
            )


def test_every_team_step_resolves_to_exactly_one_handler(tmp_path):
    features = sorted(FEATURES.glob("team_*.feature"))
    assert features, f"no team features under {FEATURES}"
    for feature in features:
        for step_text in _step_texts(_parse(feature, tmp_path)):
            matches = _matching_patterns(step_text)
            assert len(matches) == 1, (
                f"{step_text!r} in {feature.name} matched {len(matches)} handlers"
            )


def test_every_taskbreak_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "taskbreak_bridge.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, (
            f"{step_text!r} matched {len(matches)} handlers"
        )


def test_every_harness_cli_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "harness_cli.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, (
            f"{step_text!r} matched {len(matches)} handlers"
        )


def test_every_harness_wiring_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "harness_wiring.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, (
            f"{step_text!r} matched {len(matches)} handlers"
        )


def test_every_task_state_layout_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "task_state_layout.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, (
            f"{step_text!r} matched {len(matches)} handlers"
        )


def test_every_ts_wiring_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "ts_wiring.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, (
            f"{step_text!r} matched {len(matches)} handlers"
        )


def test_registered_patterns_are_unique():
    patterns = [pattern for pattern, _handler in steps.STEP_HANDLERS]
    assert len(patterns) == len(set(patterns))


def test_step_values_reads_literal_background_values():
    examples = {
        "_step_text": (
            'the orchestrator opens task "feature/periods" for role "coder"'
        )
    }
    assert common.step_values(
        examples,
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)"$',
    ) == ("feature/periods", "coder")


def test_parse_status_reads_session_load_and_cursor():
    stdout = (
        "TASK: feature/periods\nSEALED: no\n"
        "SEAT: worker session worker-2 loaded no cursor 0\n"
        "SEAT: mentor session - loaded yes cursor 7\n"
    )
    assert team_steps.parse_status(stdout) == {
        "worker": {"session": "worker-2", "loaded": False, "cursor": 0},
        "mentor": {"session": None, "loaded": True, "cursor": 7},
    }


def _refusal(stderr):
    return subprocess.CompletedProcess([], 2, "", stderr)


def _record_calls(monkeypatch, module, name):
    """Patch ``module.name`` with a successful fake that records each call's args."""
    calls = []

    def fake(world_arg, *args):
        calls.append(args)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(module, name, fake)
    return calls


def test_send_refused_full_requires_the_exact_problem_set():
    world = World()
    examples = {
        "_step_text": 'the send is refused with the problems "a; b"',
        "problems": "a; b",
    }
    world.state["mail_result"] = _refusal("MAIL ERROR:\n- a\n- b; got 2\n")
    mail_steps._send_refused_full(world, examples)
    for stderr in ("- a\n", "- a\n- b\n- extra\n", "- a\n- c\n"):
        world.state["mail_result"] = _refusal(stderr)
        with pytest.raises(AssertionError):
            mail_steps._send_refused_full(world, examples)


def test_split_items_trims_and_drops_empty_entries():
    assert mail_steps._split_items("a, b ,,c") == ["a", "b", "c"]
    assert mail_steps._split_items("") == []


def test_send_from_orchestrator_records_the_result(monkeypatch):
    world = World()
    calls = _record_calls(monkeypatch, mail_steps, "_run_mail")
    mail_steps._send_from_orchestrator(world, "--type", "note")
    assert calls == [
        ("send", "--from", "orchestrator", "--to", "coder", "--type", "note")
    ]
    assert world.state["mail_result"].returncode == 0


def test_step_values_resolves_example_placeholders():
    examples = {"_step_text": '"<role>" pulls its mail', "role": "coder"}
    assert mail_steps._step_values(
        examples, r'^"([^"]*)" pulls its mail$'
    ) == ("coder",)


def test_step_values_keeps_optional_groups_as_none():
    examples = {"_step_text": '"coder" pulls its mail', "role": "coder"}
    role, batch, session = mail_steps._step_values(
        examples,
        r'^"([^"]*)" (?:pulls|has pulled) its mail'
        r'( in batch mode)?(?: as session "([^"]*)")?$',
    )
    assert (role, batch, session) == ("coder", None, None)


def test_pull_payload_returns_the_text_after_the_header():
    stdout = "TASK: x\nPRIORITY: 50\nPAYLOAD:\nhello\nworld\n"
    assert mail_steps._pull_payload(stdout) == "hello\nworld"


def test_opened_tasks_reads_the_tool_output():
    stdout = "OPENED: cart-domain\nOPENED: cart-repo\n"
    assert taskbreak_steps._opened_tasks(stdout) == ["cart-domain", "cart-repo"]
    assert taskbreak_steps._opened_tasks("DRY RUN: no chunks opened") == []


def test_field_value_walks_nested_fields():
    doc = {"mentor": {"goal": "make it green"}}
    assert taskbreak_steps._field_value(doc, ("mentor", "goal")) == "make it green"
    assert taskbreak_steps._field_value(doc, ("missing",)) is None


def test_parse_status_rows_reads_labels_and_markers():
    stdout = (
        "PACK       [ok] /pack\n"
        "CONFIG     [ok] /pack/harness.json\n"
        "WORKSPACE  [-] /absent/project\n"
    )
    assert harness_cli_steps.parse_status_rows(stdout) == {
        "PACK": ("ok", "/pack"),
        "CONFIG": ("ok", "/pack/harness.json"),
        "WORKSPACE": ("-", "/absent/project"),
    }


def _cli_result(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


STATUS_STDOUT = (
    "PACK       [ok] /pack\n"
    "CONFIG     [ok] /pack/harness.json\n"
    "WORKSPACE  [-] /absent/project\n"
    "STATE      [-] /absent/project/.state\n"
    "ARTIFACTS  [-] /absent/project/dump\n"
    "HOT        [-] /absent/project/hot\n"
)


def test_status_row_handler_accepts_each_reported_marker():
    world = World()
    world.state["cli_result"] = _cli_result(STATUS_STDOUT)
    harness_cli_steps._status_reports_rows(world, {})
    harness_cli_steps._status_marks_row(
        world, {"_step_text": 'the status marks the PACK row as "ok"'}
    )
    harness_cli_steps._status_marks_row(
        world, {"_step_text": 'the status marks the HOT row as "-"'}
    )


def test_status_reports_rows_rejects_a_missing_label():
    world = World()
    world.state["cli_result"] = _cli_result("PACK       [ok] /pack\n")
    with pytest.raises(AssertionError):
        harness_cli_steps._status_reports_rows(world, {})


def test_status_row_handler_rejects_the_wrong_marker():
    world = World()
    world.state["cli_result"] = _cli_result(STATUS_STDOUT)
    with pytest.raises(AssertionError):
        harness_cli_steps._status_marks_row(
            world, {"_step_text": 'the status marks the PACK row as "-"'}
        )


def test_status_row_handler_rejects_an_unknown_row():
    world = World()
    world.state["cli_result"] = _cli_result(STATUS_STDOUT)
    with pytest.raises(AssertionError):
        harness_cli_steps._status_marks_row(
            world, {"_step_text": 'the status marks the GHOST row as "ok"'}
        )


def test_clean_exit_handler_reads_the_exit_code():
    world = World()
    world.state["cli_result"] = _cli_result(returncode=2, stderr="refused")
    harness_cli_steps._clean_exits_with(
        world,
        {"_step_text": "the harness clean command refuses with exit code 2"},
    )
    world.state["cli_result"] = _cli_result(returncode=0)
    harness_cli_steps._clean_exits_with(
        world,
        {"_step_text": "the harness clean command completes and exits with code 0"},
    )
    world.state["cli_result"] = _cli_result(returncode=2)
    with pytest.raises(AssertionError):
        harness_cli_steps._clean_exits_with(
            world,
            {
                "_step_text": (
                    "the harness clean command completes and exits with code 0"
                )
            },
        )


def test_refusal_reports_item_accepts_the_state_refusal():
    world = World()
    world.state["state_dir"] = Path("/tmp/proj/state")
    world.state["cli_result"] = _cli_result(
        returncode=2,
        stderr=(
            "harness: 1 in-process item(s) under /tmp/proj/state; "
            "use --force to clean anyway\n"
        ),
    )
    harness_cli_steps._refusal_reports_item(world, {})


def test_refusal_reports_item_rejects_a_usage_refusal():
    world = World()
    world.state["state_dir"] = Path("/tmp/proj/state")
    world.state["cli_result"] = _cli_result(
        returncode=2,
        stderr=(
            "usage: harness clean [-h] [--force] [{hot,state,artifacts,all}]\n"
            "harness clean: error: argument target: invalid choice: 'staTe'\n"
        ),
    )
    with pytest.raises(AssertionError):
        harness_cli_steps._refusal_reports_item(world, {})


def test_refusal_reports_item_rejects_a_wrong_state_directory():
    world = World()
    world.state["state_dir"] = Path("/tmp/proj/state")
    world.state["cli_result"] = _cli_result(
        returncode=2,
        stderr=(
            "harness: 1 in-process item(s) under /tmp/other/state; "
            "use --force to clean anyway\n"
        ),
    )
    with pytest.raises(AssertionError):
        harness_cli_steps._refusal_reports_item(world, {})


def test_managed_dir_maps_clean_targets(tmp_path):
    world = World()
    world.state["project"] = tmp_path
    world.state["managed_dirs"] = {"artifacts": tmp_path / "dump"}
    assert harness_cli_steps._managed_dir(world, "artifacts") == tmp_path / "dump"
    assert harness_cli_steps._managed_dir(world, "state") == tmp_path / "state"


def test_empty_directory_handlers_require_empty_roots(tmp_path):
    world = World()
    world.state["project"] = tmp_path
    world.state["managed_dirs"] = {
        "hot": tmp_path / "hot",
        "artifacts": tmp_path / "dump",
        "state": tmp_path / "state",
    }
    for directory in world.state["managed_dirs"].values():
        directory.mkdir()
    for target in ("hot", "artifacts", "state"):
        harness_cli_steps._dir_empty(
            world, {"_step_text": f"the project {target} directory is empty"}
        )
    (world.state["managed_dirs"]["artifacts"] / "leftover.json").write_text("{}")
    with pytest.raises(AssertionError):
        harness_cli_steps._dir_empty(
            world, {"_step_text": "the project artifacts directory is empty"}
        )


def test_no_env_overrides_clears_every_swarm_override(monkeypatch):
    names = (
        "SWARM_CONFIG",
        "SWARM_PACK",
        "SWARM_WORKSPACE",
        "SWARM_STATE_ROOT",
        "SWARM_HOT",
    )
    for name in names:
        monkeypatch.setenv(name, "set")
    wiring_steps._no_env_overrides(World(), {})
    for name in names:
        assert name not in os.environ


def test_every_durable_store_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "durable_store.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, f"{step_text!r} matched {len(matches)} handlers"


def test_every_acceptance_pipeline_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "acceptance_pipeline.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, f"{step_text!r} matched {len(matches)} handlers"


def test_every_team_open_step_resolves_to_exactly_one_handler(tmp_path):
    feature = FEATURES / "team_open_sections.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, f"{step_text!r} matched {len(matches)} handlers"


@pytest.mark.parametrize("stem", ["duplicate_dispatch", "lock_contention"])
def test_every_concurrency_step_resolves_to_exactly_one_handler(stem, tmp_path):
    feature = FEATURES / f"{stem}.feature"
    assert feature.is_file(), f"missing {feature}"
    for step_text in _step_texts(_parse(feature, tmp_path)):
        matches = _matching_patterns(step_text)
        assert len(matches) == 1, f"{step_text!r} matched {len(matches)} handlers"


# --- durable store, pipeline, and open-section handlers --------------------


def test_durable_store_listing_handler_compares_names():
    world = World()
    durable_store_steps._directory_holds(
        world,
        {"_step_text": 'the durable store directory holds the files "b.json,a.json"'},
    )
    durable_store_steps._list_directory(world, {})
    durable_store_steps._listing_is(
        world, {"_step_text": 'the listing is "a.json,b.json"'}
    )
    with pytest.raises(AssertionError):
        durable_store_steps._listing_is(
            world, {"_step_text": 'the listing is "a.json"'}
        )


def test_durable_store_sequence_handler_reads_start_and_calls():
    world = World()
    durable_store_steps._counter_starts(
        world, {"_step_text": "the durable store counter starts at 4"}
    )
    durable_store_steps._allocate_sequences(
        world, {"_step_text": "the durable store allocates 2 sequence numbers"}
    )
    durable_store_steps._sequences_are(
        world, {"_step_text": 'the allocated sequence numbers are "5,6"'}
    )
    with pytest.raises(AssertionError):
        durable_store_steps._sequences_are(
            world, {"_step_text": 'the allocated sequence numbers are "5"'}
        )


def test_durable_store_lock_handler_reports_contention():
    world = World()
    durable_store_steps._second_holder_requests(
        world,
        {
            "_step_text": (
                'a second holder requests the lock "mailbox" while the store '
                'holds the lock "mailbox"'
            )
        },
    )
    assert world.state["second_blocked"] is True
    durable_store_steps._second_holder_outcome(
        world, {"_step_text": "the second holder is blocked"}
    )
    with pytest.raises(AssertionError):
        durable_store_steps._second_holder_outcome(
            world, {"_step_text": "the second holder is admitted"}
        )


def test_durable_store_lock_handler_admits_a_different_name():
    world = World()
    durable_store_steps._second_holder_requests(
        world,
        {
            "_step_text": (
                'a second holder requests the lock "journal" while the store '
                'holds the lock "mailbox"'
            )
        },
    )
    assert world.state["second_blocked"] is False


def test_durable_store_cli_handler_renders_problem_lines():
    world = World()
    durable_store_steps._cli_refuses(
        world,
        {"_step_text": 'the durable store CLI refuses with the problems "first;second"'},
    )
    durable_store_steps._cli_exits_with(
        world, {"_step_text": "the durable store CLI exits with code 2"}
    )
    durable_store_steps._cli_problem_lines(
        world,
        {
            "_step_text": (
                'the durable store CLI prints the problem lines '
                '"- first;- second"'
            )
        },
    )
    with pytest.raises(AssertionError):
        durable_store_steps._cli_exits_with(
            world, {"_step_text": "the durable store CLI exits with code 1"}
        )


def test_pipeline_dry_report_handler_reads_finding_kinds():
    world = World()
    world.state["dry_report"] = {"findings": [{"kind": "duplicate-in-scenario"}]}
    acceptance_pipeline_steps._dry_report_finding(
        world,
        {"_step_text": 'the dry report reports a "duplicate-in-scenario" finding'},
    )
    acceptance_pipeline_steps._dry_report_finding(
        world,
        {"_step_text": 'the dry report does not report a "exact-duplicate" finding'},
    )
    with pytest.raises(AssertionError):
        acceptance_pipeline_steps._dry_report_finding(
            world,
            {"_step_text": 'the dry report reports a "exact-duplicate" finding'},
        )


def test_pipeline_dry_report_kinds_handler_requires_the_exact_set():
    world = World()
    world.state["dry_report"] = {
        "findings": [
            {"kind": "duplicate-in-scenario"},
            {"kind": "duplicate-in-scenario"},
        ]
    }
    acceptance_pipeline_steps._dry_report_kinds(
        world,
        {
            "_step_text": (
                'the dry report contains only the "duplicate-in-scenario" kinds'
            )
        },
    )
    world.state["dry_report"]["findings"].append({"kind": "exact-duplicate"})
    with pytest.raises(AssertionError):
        acceptance_pipeline_steps._dry_report_kinds(
            world,
            {
                "_step_text": (
                    'the dry report contains only the '
                    '"duplicate-in-scenario" kinds'
                )
            },
        )


def test_pipeline_dry_report_kinds_handler_accepts_a_multi_kind_set():
    world = World()
    world.state["dry_report"] = {
        "findings": [
            {"kind": "duplicate-in-scenario"},
            {"kind": "exact-duplicate"},
        ]
    }
    acceptance_pipeline_steps._dry_report_kinds(
        world,
        {
            "_step_text": (
                'the dry report contains only the '
                '"duplicate-in-scenario, exact-duplicate" kinds'
            )
        },
    )


def test_pipeline_parsed_step_handler_reads_parameters():
    world = World()
    world.state["parsed_ir"] = {
        "name": "Login",
        "scenarios": [
            {
                "name": "Login works",
                "steps": [
                    {
                        "keyword": "Given",
                        "text": "the user is <user>",
                        "parameters": ["user"],
                    }
                ],
            }
        ],
    }
    acceptance_pipeline_steps._parsed_name(
        world, {"_step_text": 'the parsed feature is named "Login"'}
    )
    acceptance_pipeline_steps._parsed_step(
        world,
        {
            "_step_text": (
                'the parsed step is "<step>" with parameter "<parameter>"'
            ),
            "step": "the user is <user>",
            "parameter": "user",
        },
    )
    with pytest.raises(AssertionError):
        acceptance_pipeline_steps._parsed_step(
            world,
            {
                "_step_text": (
                    'the parsed step is "<step>" with parameter "<parameter>"'
                ),
                "step": "the user is <user>",
                "parameter": "ghost",
            },
        )


def test_durable_store_lock_handler_rejects_an_unknown_outcome():
    world = World()
    world.state["second_blocked"] = True
    with pytest.raises(AssertionError):
        durable_store_steps._second_holder_outcome(
            world, {"_step_text": "the second holder vanishes"}
        )


def test_pipeline_dry_report_rejects_an_unknown_outcome():
    world = World()
    world.state["dry_report"] = {"findings": []}
    with pytest.raises(AssertionError):
        acceptance_pipeline_steps._dry_report_finding(
            world, {"_step_text": 'the dry report ignores a "duplicate" finding'}
        )


def test_team_open_styled_task_rejects_an_unknown_heading_style():
    world = World()
    with pytest.raises(AssertionError):
        team_open_steps._brief_styled_task(
            world,
            {
                "_step_text": 'a brief with a "italic" TASK heading reading "goal"',
            },
        )


def test_selected_kind_handler_checks_the_chosen_root(tmp_path):
    resolved = SimpleNamespace(
        persistent_tests=(
            {"root": tmp_path / "harness", "kind": "harness"},
            {"root": tmp_path / "project", "kind": "project"},
        )
    )
    world = World()
    world.state["resolved"] = resolved
    world.state["selected_persistent"] = tmp_path / "harness"
    wiring_steps._selected_kind(
        world, {"_step_text": 'the selected persistent root has kind "harness"'}
    )
    with pytest.raises(AssertionError):
        wiring_steps._selected_kind(
            world, {"_step_text": 'the selected persistent root has kind "project"'}
        )


def test_ts_wiring_report_handlers_check_the_resolved_config(tmp_path):
    world = World()
    world.state["config"] = tmp_path / "harness.json"
    world.state["ts_config"] = (tmp_path / "harness.json").resolve()
    ts_wiring_steps._reports_project_config(world, {})
    with pytest.raises(AssertionError):
        world.state["ts_config"] = (tmp_path / "other.json").resolve()
        ts_wiring_steps._reports_project_config(world, {})

    world.state["ts_config"] = (wiring.PACK_ROOT / "harness.json").resolve()
    ts_wiring_steps._reports_pack_config(world, {})
    with pytest.raises(AssertionError):
        world.state["ts_config"] = tmp_path / "harness.json"
        ts_wiring_steps._reports_pack_config(world, {})


# --- audited mail, team, and harness clean handlers ------------------------


def test_completion_refusal_requires_a_refusal_naming_the_owner():
    world = World()
    world.state["mail_result"] = _refusal(
        "MAIL ERROR:\n"
        "- `coder` in-process mail is owned by session session-a; "
        "refusing to complete\n"
    )
    mail_steps._completion_refusal(
        world,
        {"_step_text": 'the completion refusal names "owned by session session-a"'},
    )
    world.state["mail_result"] = _cli_result(returncode=0)
    with pytest.raises(AssertionError):
        mail_steps._completion_refusal(
            world,
            {"_step_text": 'the completion refusal names "owned by session session-a"'},
        )


def test_done_first_in_process_uses_status_then_done_id(monkeypatch):
    world = World()
    calls = []

    def fake_run_mail(world_arg, *args):
        calls.append(args)
        if args[:2] == ("status", "--role"):
            payload = {"roles": {"coder": {"in_process": [{"id": "mail-1"}]}}}
            return subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(mail_steps, "_run_mail", fake_run_mail)
    mail_steps._mail_done_first_in_process(
        world, {"_step_text": '"coder" completes the first in-process mail'}
    )
    assert calls[0] == ("status", "--role", "coder", "--json")
    assert calls[1] == ("done", "--as", "coder", "--id", "mail-1")


def test_status_holder_session_reads_the_recorded_status():
    world = World()
    world.state["mail_status_role"] = "coder"
    world.state["mail_status"] = {
        "roles": {"coder": {"in_process": [{"owner": "session-a"}]}}
    }
    mail_steps._status_holder_session(
        world, {"_step_text": 'the status reports holder session "session-a"'}
    )
    world.state["mail_status"]["roles"]["coder"]["in_process"][0]["owner"] = "session-b"
    with pytest.raises(AssertionError):
        mail_steps._status_holder_session(
            world, {"_step_text": 'the status reports holder session "session-a"'}
        )


def test_team_refusal_requires_a_refusal_naming_the_problem():
    world = World()
    world.state["team_result"] = _refusal(
        "TEAM ERROR:\n- role must be one of: orchestrator, coder\n"
    )
    team_steps._team_refusal(
        world, {"_step_text": 'the team refusal names "role must be one of:"'}
    )
    world.state["team_result"] = _cli_result(returncode=0)
    with pytest.raises(AssertionError):
        team_steps._team_refusal(
            world, {"_step_text": 'the team refusal names "role must be one of:"'}
        )


def test_attempt_open_records_a_refused_result(monkeypatch):
    world = World()
    calls = []

    def fake_run_team(world_arg, *args):
        calls.append(args)
        return subprocess.CompletedProcess([], 2, "", "TEAM ERROR")

    monkeypatch.setattr(team_steps, "_run_team", fake_run_team)
    team_steps._orchestrator_attempts_open(
        world,
        {
            "_step_text": (
                'the orchestrator attempts to open task "c1" for role "manager"'
            )
        },
    )
    assert calls == [("open", "c1", "--role", "manager")]
    assert world.state["team_result"].returncode == 2


def test_mentor_journals_entry_records_a_refused_result(monkeypatch):
    world = World()
    world.state["team_sessions"] = {"worker": "worker-1", "mentor": "mentor-1"}
    calls = []

    def fake_run_team(world_arg, *args):
        calls.append(args)
        return subprocess.CompletedProcess([], 2, "", "only the worker seat")

    monkeypatch.setattr(team_steps, "_run_team", fake_run_team)
    team_steps._mentor_journals_entry(
        world, {"_step_text": 'the mentor seat journals a "plan" entry'}
    )
    assert calls[0][:4] == ("journal", "--session", "mentor-1", "--kind")
    assert calls[0][4] == "plan"
    assert world.state["journal_result"].returncode == 2


def test_clean_default_handler_runs_clean_without_a_target(monkeypatch):
    world = World()
    calls = []

    def fake_run_harness(world_arg, *args):
        calls.append(args)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(harness_cli_steps, "_run_harness", fake_run_harness)
    harness_cli_steps._run_clean_default(world, {})
    assert calls == [("clean",)]


def test_verify_queued_checks_each_queued_document(monkeypatch):
    world = World()
    docs = {
        "coder": [
            {"from": "orchestrator", "priority": "50", "message": "go", "task": "t"}
        ]
    }
    monkeypatch.setattr(
        mail_steps, "_mail_docs", lambda w, role, state: docs.get(role, [])
    )
    mail_steps._verify_queued(world, "orchestrator", "coder", "t", "50", "go")
    with pytest.raises(AssertionError):
        mail_steps._verify_queued(world, "orchestrator", "ghost", "t", "50", "go")
    with pytest.raises(AssertionError):
        mail_steps._verify_queued(world, "other", "coder", "t", "50", "go")


def test_last_journal_entry_reads_the_final_non_blank_line(monkeypatch, tmp_path):
    world = World()
    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"seq": 1}\n\n{"seq": 2}\n')
    monkeypatch.setattr(team_steps, "_chunk_dir", lambda w, task=None: tmp_path)
    assert team_steps._last_journal_entry(world) == {"seq": 2}

    journal.write_text("\n")
    with pytest.raises(AssertionError):
        team_steps._last_journal_entry(world)


def test_only_dir_requires_exactly_one_subdirectory(tmp_path):
    (tmp_path / "only").mkdir()
    assert common._only_dir(tmp_path) == tmp_path / "only"
    (tmp_path / "second").mkdir()
    with pytest.raises(AssertionError):
        common._only_dir(tmp_path)


def test_mail_done_as_session_records_the_result(monkeypatch):
    world = World()
    calls = _record_calls(monkeypatch, mail_steps, "_run_mail")
    mail_steps._mail_done_as_session(
        world, {"_step_text": '"coder" completes its mail as session "s1"'}
    )
    assert calls == [("done", "--as", "coder", "--session", "s1")]
    assert world.state["mail_result"].returncode == 0

