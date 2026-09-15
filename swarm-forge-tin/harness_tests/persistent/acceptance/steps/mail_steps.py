"""Step handlers for the mail queue and send validation acceptance features."""

import json
import subprocess

from runtime import World

from .common import _run_together, _run_tool, _state_root, assert_refused
from .common import step_values as _step_values

MAIL = "mailbox.py"
_PAYLOAD_HEADER = "PAYLOAD:"
_COUNT_KEYS = {"queued": "new", "in-process": "in_process", "completed": "completed"}


def _run_mail(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run mailbox.py CLI on the temp project and return the result."""
    return _run_tool(world, MAIL, *args)


def _mail_inbox(world: World, role: str, state: str):
    return _state_root(world) / "mail" / "inbox" / role / state


def _mail_docs(world: World, role: str, state: str) -> list[dict]:
    directory = _mail_inbox(world, role, state)
    if not directory.is_dir():
        return []
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def _mailbox_counts(world: World, role: str) -> dict:
    result = _run_mail(world, "status", "--role", role, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["roles"][role]["counts"]


def _split_items(value: str) -> list[str]:
    """Split a comma-separated step value into non-empty stripped items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _verify_queued(
    world: World,
    sender: str,
    recipients: str,
    task: str | None,
    priority: str,
    message: str | None,
) -> None:
    """Assert the queued items carry the values the send step asked for."""
    for role in _split_items(recipients):
        matches = [
            doc for doc in _mail_docs(world, role, "new") if doc.get("task") == task
        ]
        assert matches, f"no queued mail for {role} with task {task!r}"
        doc = matches[0]
        assert doc["from"] == sender, f"queued sender {doc['from']!r} != {sender!r}"
        assert doc["priority"] == priority, (
            f"queued priority {doc['priority']!r} != {priority!r}"
        )
        if message is not None:
            assert doc.get("message") == message, (
                f"queued message {doc.get('message')!r} != {message!r}"
            )


def _pull_payload(stdout: str) -> str:
    lines = stdout.splitlines()
    index = lines.index(_PAYLOAD_HEADER)
    return "\n".join(lines[index + 1:])


def _mail_send_handoff(world: World, examples: dict[str, str]) -> None:
    sender, to, task, priority, message = _step_values(
        examples,
        r'^mail is sent from "([^"]*)" to "([^"]*)" as a handoff for task '
        r'"([^"]*)" with priority "([^"]*)" and message "([^"]*)"$',
    )
    args = [
        "send", "--from", sender, "--to", to, "--type", "handoff",
        "--task", task, "--priority", priority,
    ]
    if message is not None:
        args += ["--message", message]
    result = _run_mail(world, *args)
    world.state["mail_result"] = result
    world.state["mail_last_send"] = args
    if result.returncode == 0:
        _verify_queued(world, sender, to, task, priority, message)


def _mail_send_note(world: World, examples: dict[str, str]) -> None:
    sender, to, message = _step_values(
        examples,
        r'^mail is sent from "([^"]*)" to "([^"]*)" as a note with message "([^"]*)"$',
    )
    args = ["send", "--from", sender, "--to", to, "--type", "note", "--message", message]
    result = _run_mail(world, *args)
    world.state["mail_result"] = result
    world.state["mail_last_send"] = args
    if result.returncode == 0:
        _verify_queued(world, sender, to, None, "50", message)


def _that_mail_sent_again(world: World, examples: dict[str, str]) -> None:
    world.state["mail_result"] = _run_mail(world, *world.state["mail_last_send"])


def _send_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = _step_values(examples, r'^the send reports "([^"]*)"$')
    assert expected in world.state["mail_result"].stdout


def _send_reports_recipients(world: World, examples: dict[str, str]) -> None:
    (expected,) = _step_values(
        examples, r'^the send reports the recipients "([^"]*)"$'
    )
    assert f"TO: {expected}" in world.state["mail_result"].stdout


def _send_refused(world: World, examples: dict[str, str]) -> None:
    (problem,) = _step_values(
        examples, r'^the send is refused with a problem naming "([^"]*)"$'
    )
    result = world.state["mail_result"]
    assert result.returncode == 2, f"send was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _stderr_problems(stderr: str) -> list[str]:
    """Return the ``- `` problem lines a tool wrote to stderr, in order."""
    return [line[2:] for line in stderr.splitlines() if line.startswith("- ")]


def _send_refused_full(world: World, examples: dict[str, str]) -> None:
    (problems,) = _step_values(
        examples, r'^the send is refused with the problems "([^"]*)"$'
    )
    result = world.state["mail_result"]
    assert result.returncode == 2, f"send was not refused: {result.stdout}"
    expected = problems.split("; ")
    actual = _stderr_problems(result.stderr)
    assert len(actual) == len(expected), (
        f"problem count {len(actual)} != {len(expected)}: {actual!r}"
    )
    for want, got in zip(expected, actual):
        assert got.startswith(want), f"problem {got!r} does not name {want!r}"


def _no_mail_queued(world: World, examples: dict[str, str]) -> None:
    (role,) = _step_values(examples, r'^no mail is queued for "([^"]*)"$')
    assert _mailbox_counts(world, role)["new"] == 0


def _mailbox_count(world: World, examples: dict[str, str]) -> None:
    role, state_word, count = _step_values(
        examples,
        r'^the "([^"]*)" mailbox (queued|in-process|completed) count is "([^"]*)"$',
    )
    actual = _mailbox_counts(world, role)[_COUNT_KEYS[state_word]]
    assert str(actual) == count, f"{state_word} count {actual} != {count}"


def _mails_are_queued(world: World, examples: dict[str, str]) -> None:
    mails, role = _step_values(
        examples, r'^mails "([^"]*)" are queued to "([^"]*)"$'
    )
    world.state["mail_role"] = role
    expected = []
    for item in _split_items(mails):
        task, priority = item.rsplit("@", 1)
        result = _run_mail(
            world, "send", "--from", "orchestrator", "--to", role,
            "--type", "handoff", "--task", task, "--priority", priority,
            "--message", task,
        )
        assert result.returncode == 0, result.stderr
        expected.append((task, priority))
    actual = [(doc["task"], doc["priority"]) for doc in _mail_docs(world, role, "new")]
    assert sorted(actual) == sorted(expected), (
        f"queued {actual} != expected {expected}"
    )


def _mail_pull(world: World, examples: dict[str, str]) -> None:
    role, batch, session = _step_values(
        examples,
        r'^"([^"]*)" (?:pulls|has pulled) its mail'
        r'( in batch mode)?(?: as session "([^"]*)")?$',
    )
    args = ["pull", "--as", role]
    if batch:
        args += ["--mode", "batch"]
    if session:
        args += ["--session", session]
    world.state["mail_role"] = role
    result = _run_mail(world, *args)
    world.state["mail_result"] = result
    world.state["pull_result"] = result


def _mail_takeover(world: World, examples: dict[str, str]) -> None:
    role, session = _step_values(
        examples, r'^"([^"]*)" takes over its mail as session "([^"]*)"$'
    )
    result = _run_mail(
        world, "pull", "--as", role, "--session", session, "--takeover"
    )
    world.state["mail_result"] = result
    world.state["pull_result"] = result


def _pull_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = _step_values(examples, r'^the pull reports "([^"]*)"$')
    result = world.state.get("pull_result") or world.state["mail_result"]
    assert expected in result.stdout


def _pull_reports_batch(world: World, examples: dict[str, str]) -> None:
    (count,) = _step_values(
        examples, r'^the pull reports a batch of "([^"]*)" items$'
    )
    assert f"COUNT: {count}" in world.state["mail_result"].stdout


def _pulled_task_is(world: World, examples: dict[str, str]) -> None:
    (task,) = _step_values(examples, r'^the pulled task is "([^"]*)"$')
    assert f"TASK_NAME: {task}" in world.state["mail_result"].stdout


def _pulled_priority_is(world: World, examples: dict[str, str]) -> None:
    (priority,) = _step_values(examples, r'^the pulled priority is "([^"]*)"$')
    assert f"PRIORITY: {priority}" in world.state["mail_result"].stdout


def _batch_priority_is(world: World, examples: dict[str, str]) -> None:
    (priority,) = _step_values(examples, r'^the batch priority is "([^"]*)"$')
    assert f"PRIORITY: {priority}" in world.state["mail_result"].stdout


def _pull_refused(world: World, examples: dict[str, str]) -> None:
    (problem,) = _step_values(
        examples, r'^the pull is refused with a problem naming "([^"]*)"$'
    )
    result = world.state["mail_result"]
    assert result.returncode == 2, f"pull was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _pulled_payload_names_task(world: World, examples: dict[str, str]) -> None:
    (task,) = _step_values(examples, r'^the pulled payload names task "([^"]*)"$')
    assert f"TASK_NAME: {task}" in world.state["mail_result"].stdout


def _pulled_payload_carries(world: World, examples: dict[str, str]) -> None:
    (message,) = _step_values(examples, r'^the pulled payload carries "([^"]*)"$')
    assert message in _pull_payload(world.state["mail_result"].stdout)


def _pulled_payload_is(world: World, examples: dict[str, str]) -> None:
    (message,) = _step_values(examples, r'^the pulled payload is "([^"]*)"$')
    assert _pull_payload(world.state["mail_result"].stdout) == message


def _mail_done(world: World, examples: dict[str, str]) -> None:
    role, result_value = _step_values(
        examples, r'^"([^"]*)" completes its mail with result "([^"]*)"$'
    )
    result = _run_mail(world, "done", "--as", role, "--result", result_value)
    world.state["mail_result"] = result
    if result.returncode == 0:
        docs = _mail_docs(world, role, "completed")
        assert any(doc.get("result") == result_value for doc in docs), (
            f"completed items do not record result {result_value!r}"
        )


def _completion_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = _step_values(examples, r'^the completion reports "([^"]*)"$')
    assert expected in world.state["mail_result"].stdout


def _completed_records_result(world: World, examples: dict[str, str]) -> None:
    (result_value,) = _step_values(
        examples, r'^the completed item records result "([^"]*)"$'
    )
    docs = _mail_docs(world, "coder", "completed")
    assert any(doc.get("result") == result_value for doc in docs)


def _mail_done_as_session(world: World, examples: dict[str, str]) -> None:
    role, session = _step_values(
        examples, r'^"([^"]*)" completes its mail as session "([^"]*)"$'
    )
    world.state["mail_result"] = _run_mail(
        world, "done", "--as", role, "--session", session
    )


def _completion_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = _step_values(
        examples, r'^the completion refusal names "([^"]*)"$'
    )
    assert_refused(world.state["mail_result"], problem, "completion")


def _corrupt_mail_item_queued(world: World, examples: dict[str, str]) -> None:
    """Queue a single unreadable item so the next pull must fail closed."""
    (role,) = _step_values(examples, r'^a corrupt mail item is queued to "([^"]*)"$')
    new_dir = _mail_inbox(world, role, "new")
    new_dir.mkdir(parents=True, exist_ok=True)
    path = new_dir / "50_corrupt.json"
    path.write_text("{not json")
    world.state["mail_role"] = role
    world.state["corrupt_mail_path"] = path


def _in_process_mail_item_corrupted(world: World, examples: dict[str, str]) -> None:
    """Corrupt the pulled item so the next completion must fail closed."""
    role = world.state.get("mail_role", "coder")
    items = sorted(_mail_inbox(world, role, "in_process").glob("*.json"))
    assert items, f"no in-process mail for {role}"
    items[0].write_text("{not json")
    world.state["corrupt_mail_path"] = items[0]


def _corrupt_mail_item_still_queued(world: World, examples: dict[str, str]) -> None:
    path = world.state["corrupt_mail_path"]
    assert path.is_file() and path.parent.name == "new", (
        f"corrupt item is not still queued: {path}"
    )


def _corrupt_mail_item_still_in_process(world: World, examples: dict[str, str]) -> None:
    path = world.state["corrupt_mail_path"]
    assert path.is_file() and path.parent.name == "in_process", (
        f"corrupt item is not still in process: {path}"
    )


def _mail_done_first_in_process(world: World, examples: dict[str, str]) -> None:
    (role,) = _step_values(
        examples, r'^"([^"]*)" completes the first in-process mail$'
    )
    status = _run_mail(world, "status", "--role", role, "--json")
    assert status.returncode == 0, status.stderr
    holding = json.loads(status.stdout)["roles"][role]["in_process"]
    assert holding, f"no in-process mail for {role}"
    world.state["mail_result"] = _run_mail(
        world, "done", "--as", role, "--id", holding[0]["id"]
    )


def _status_holder_session(world: World, examples: dict[str, str]) -> None:
    (owner,) = _step_values(
        examples, r'^the status reports holder session "([^"]*)"$'
    )
    role = world.state["mail_status_role"]
    assert role, "a holder session needs a role-specific status read"
    holding = world.state["mail_status"]["roles"][role]["in_process"]
    assert holding and holding[0]["owner"] == owner, (
        f"holder is not {owner!r}: {holding!r}"
    )


def _status_for_role(world: World, examples: dict[str, str]) -> None:
    (role,) = _step_values(examples, r'^mail status is read for "([^"]*)"$')
    result = _run_mail(world, "status", "--role", role, "--json")
    assert result.returncode == 0, result.stderr
    world.state["mail_status"] = json.loads(result.stdout)
    world.state["mail_status_role"] = role


def _status_for_all_roles(world: World, examples: dict[str, str]) -> None:
    result = _run_mail(world, "status", "--json")
    assert result.returncode == 0, result.stderr
    world.state["mail_status"] = json.loads(result.stdout)
    world.state["mail_status_role"] = None


def _status_names_role(world: World, examples: dict[str, str]) -> None:
    (role,) = _step_values(examples, r'^the status names role "([^"]*)"$')
    assert role in world.state["mail_status"]["roles"]


def _status_count_is(world: World, examples: dict[str, str]) -> None:
    state_word, count = _step_values(
        examples, r'^the status (queued|in-process) count is "([^"]*)"$'
    )
    role = world.state["mail_status_role"]
    assert role, "a status count needs a role-specific status read"
    actual = world.state["mail_status"]["roles"][role]["counts"][_COUNT_KEYS[state_word]]
    assert str(actual) == count, f"{state_word} count {actual} != {count}"


def _in_process_owner_is(world: World, examples: dict[str, str]) -> None:
    role, owner = _step_values(
        examples, r'^the "([^"]*)" in-process owner is "([^"]*)"$'
    )
    result = _run_mail(world, "status", "--role", role, "--json")
    assert result.returncode == 0, result.stderr
    items = json.loads(result.stdout)["roles"][role]["in_process"]
    assert items and items[0]["owner"] == owner, f"owner is not {owner!r}"


def _send_from_orchestrator(world: World, *args: str) -> None:
    """Send from the orchestrator to the coder and record the result."""
    world.state["mail_result"] = _run_mail(
        world, "send", "--from", "orchestrator", "--to", "coder", *args
    )


def _handoff_without_task(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(world, "--type", "handoff", "--priority", "50")


def _handoff_over_long_task(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(
        world, "--type", "handoff", "--task", "x" * 81, "--priority", "50"
    )


def _note_without_message(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(world, "--type", "note")


def _note_over_long_message(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(world, "--type", "note", "--message", "x" * 81)


def _handoff_over_long_message(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(
        world, "--type", "handoff", "--task", "feature/periods",
        "--priority", "50", "--message", "x" * 301,
    )


def _handoff_multiline_message(world: World, examples: dict[str, str]) -> None:
    _send_from_orchestrator(
        world, "--type", "handoff", "--task", "feature/periods",
        "--priority", "50", "--message", "first line\nsecond line",
    )


def _handoff_builtin_sender(world: World, examples: dict[str, str]) -> None:
    world.state["mail_result"] = _run_mail(
        world, "send", "--from", "build", "--to", "coder",
        "--type", "handoff", "--task", "feature/periods", "--priority", "50",
        "--message", "start",
    )


# --- concurrency -----------------------------------------------------------


def _simultaneous_pull(world: World, examples: dict[str, str]) -> None:
    """Two sessions pull one role's mail as separate processes at the same time."""
    first, second, role = _step_values(
        examples,
        r'^sessions "([^"]*)" and "([^"]*)" pull the "([^"]*)" mail at the same time$',
    )
    world.state["mail_role"] = role
    world.state["pull_sessions"] = [first, second]
    world.state["pull_results"] = _run_together(
        world,
        [
            (MAIL, ("pull", "--as", role, "--session", first), None),
            (MAIL, ("pull", "--as", role, "--session", second), None),
        ],
    )


def _exactly_one_session_claims(world: World, examples: dict[str, str]) -> None:
    """Exactly one concurrent pull exited cleanly and owns the item."""
    results = world.state["pull_results"]
    sessions = world.state["pull_sessions"]
    claimed = [
        session for session, result in zip(sessions, results)
        if result.returncode == 0
    ]
    assert len(claimed) == 1, (
        f"claims {claimed!r} from "
        f"{[(s, r.returncode) for s, r in zip(sessions, results)]}"
    )
    world.state["winning_session"] = claimed[0]
    items = _mail_docs(world, world.state["mail_role"], "in_process")
    assert len(items) == 1, f"in-process items: {items!r}"
    assert items[0]["owner_session"] == claimed[0], items[0]["owner_session"]


def _losing_session_refused(world: World, examples: dict[str, str]) -> None:
    """The non-claiming pull was refused naming the winning session."""
    results = world.state["pull_results"]
    sessions = world.state["pull_sessions"]
    winner = world.state["winning_session"]
    losers = [result for session, result in zip(sessions, results) if session != winner]
    assert len(losers) == 1, f"losers: {losers!r}"
    loser = losers[0]
    assert loser.returncode == 2, f"loser was not refused: {loser.stdout}"
    assert f"owned by session {winner}" in loser.stderr, loser.stderr


def _simultaneous_identical_sends(world: World, examples: dict[str, str]) -> None:
    """Two identical handoffs are sent as separate processes at the same time."""
    task, role = _step_values(
        examples,
        r'^two identical handoffs for task "([^"]*)" are sent to "([^"]*)" '
        r"at the same time$",
    )
    world.state["mail_role"] = role
    args = (
        "send", "--from", "orchestrator", "--to", role, "--type", "handoff",
        "--task", task, "--priority", "50", "--message", task,
    )
    world.state["send_results"] = _run_together(
        world, [(MAIL, args, None), (MAIL, args, None)]
    )


def _exactly_one_send_queues(world: World, examples: dict[str, str]) -> None:
    """Exactly one of the concurrent identical sends queued a new item."""
    results = world.state["send_results"]
    queued = [result for result in results if "QUEUED:" in result.stdout]
    assert len(queued) == 1, [result.stdout for result in results]


HANDLERS = [
    (
        r'^mail is sent from "([^"]*)" to "([^"]*)" as a handoff for task '
        r'"([^"]*)" with priority "([^"]*)" and message "([^"]*)"$',
        _mail_send_handoff,
    ),
    (
        r'^mail is sent from "([^"]*)" to "([^"]*)" as a note with message "([^"]*)"$',
        _mail_send_note,
    ),
    (r"^that mail is sent again$", _that_mail_sent_again),
    (r'^the send reports "([^"]*)"$', _send_reports),
    (r'^the send reports the recipients "([^"]*)"$', _send_reports_recipients),
    (r'^the send is refused with a problem naming "([^"]*)"$', _send_refused),
    (r'^the send is refused with the problems "([^"]*)"$', _send_refused_full),
    (r'^no mail is queued for "([^"]*)"$', _no_mail_queued),
    (
        r'^the "([^"]*)" mailbox (queued|in-process|completed) count is "([^"]*)"$',
        _mailbox_count,
    ),
    (r'^mails "([^"]*)" are queued to "([^"]*)"$', _mails_are_queued),
    (
        r'^"([^"]*)" (?:pulls|has pulled) its mail'
        r'( in batch mode)?(?: as session "([^"]*)")?$',
        _mail_pull,
    ),
    (
        r'^"([^"]*)" takes over its mail as session "([^"]*)"$',
        _mail_takeover,
    ),
    (r'^the pull reports "([^"]*)"$', _pull_reports),
    (r'^the pull reports a batch of "([^"]*)" items$', _pull_reports_batch),
    (r'^the pulled task is "([^"]*)"$', _pulled_task_is),
    (r'^the pulled priority is "([^"]*)"$', _pulled_priority_is),
    (r'^the batch priority is "([^"]*)"$', _batch_priority_is),
    (r'^the pull is refused with a problem naming "([^"]*)"$', _pull_refused),
    (r'^the pulled payload names task "([^"]*)"$', _pulled_payload_names_task),
    (r'^the pulled payload carries "([^"]*)"$', _pulled_payload_carries),
    (r'^the pulled payload is "([^"]*)"$', _pulled_payload_is),
    (
        r'^"([^"]*)" completes its mail with result "([^"]*)"$',
        _mail_done,
    ),
    (
        r'^"([^"]*)" completes its mail as session "([^"]*)"$',
        _mail_done_as_session,
    ),
    (r'^the completion refusal names "([^"]*)"$', _completion_refusal),
    (r'^a corrupt mail item is queued to "([^"]*)"$', _corrupt_mail_item_queued),
    (r"^the in-process mail item is corrupted$", _in_process_mail_item_corrupted),
    (r"^the corrupt mail item is still queued$", _corrupt_mail_item_still_queued),
    (
        r"^the corrupt mail item is still in process$",
        _corrupt_mail_item_still_in_process,
    ),
    (
        r'^"([^"]*)" completes the first in-process mail$',
        _mail_done_first_in_process,
    ),
    (r'^the completion reports "([^"]*)"$', _completion_reports),
    (r'^the completed item records result "([^"]*)"$', _completed_records_result),
    (r'^mail status is read for "([^"]*)"$', _status_for_role),
    (r"^mail status is read for all roles$", _status_for_all_roles),
    (r'^the status names role "([^"]*)"$', _status_names_role),
    (r'^the status (queued|in-process) count is "([^"]*)"$', _status_count_is),
    (r'^the status reports holder session "([^"]*)"$', _status_holder_session),
    (r'^the "([^"]*)" in-process owner is "([^"]*)"$', _in_process_owner_is),
    (r"^a handoff without a task is sent$", _handoff_without_task),
    (r"^a handoff with an over-long task is sent$", _handoff_over_long_task),
    (r"^a note without a message is sent$", _note_without_message),
    (r"^a note with an over-long message is sent$", _note_over_long_message),
    (r"^a handoff with an over-long message is sent$", _handoff_over_long_message),
    (r"^a handoff with a multi-line message is sent$", _handoff_multiline_message),
    (r"^a handoff is sent from the builtin sender$", _handoff_builtin_sender),
    (
        r'^sessions "([^"]*)" and "([^"]*)" pull the "([^"]*)" mail '
        r"at the same time$",
        _simultaneous_pull,
    ),
    (r"^exactly one session claims the item$", _exactly_one_session_claims),
    (
        r"^the losing session is refused naming the winning session$",
        _losing_session_refused,
    ),
    (
        r'^two identical handoffs for task "([^"]*)" are sent to "([^"]*)" '
        r"at the same time$",
        _simultaneous_identical_sends,
    ),
    (r"^exactly one send queues the item$", _exactly_one_send_queues),
]
