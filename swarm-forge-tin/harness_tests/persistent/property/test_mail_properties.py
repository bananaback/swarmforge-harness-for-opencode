"""Property tests for the mail tool's content-identity (dedup) invariant."""

import json
import mailbox
import shutil
import string
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

TEXT = st.text(alphabet=string.ascii_lowercase + " /._-", min_size=1, max_size=20)
SETTINGS = settings(max_examples=50, deadline=None)
FIXTURE_SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@SETTINGS
@given(sender=TEXT, mtype=st.sampled_from(mailbox.TYPES), task=TEXT, message=TEXT)
def test_identical_content_has_a_stable_identity(sender, mtype, task, message):
    first = mailbox.message_hash(sender, mtype, task, message)
    second = mailbox.message_hash(sender, mtype, task, message)
    assert first == second


@SETTINGS
@given(sender=TEXT, task=TEXT, message=TEXT, other=TEXT)
def test_a_different_message_changes_the_identity(sender, task, message, other):
    assume(message != other)
    assert mailbox.message_hash(sender, "handoff", task, message) != mailbox.message_hash(
        sender, "handoff", task, other
    )


@SETTINGS
@given(sender=TEXT, mtype=st.sampled_from(mailbox.TYPES), task=TEXT, message=TEXT, other=TEXT)
def test_a_different_sender_changes_the_identity(sender, mtype, task, message, other):
    assume(sender != other)
    assert mailbox.message_hash(sender, mtype, task, message) != mailbox.message_hash(
        other, mtype, task, message
    )


@SETTINGS
@given(task=TEXT, message=TEXT)
def test_handoff_payload_names_the_task_and_carries_the_message(task, message):
    payload = mailbox.build_payload(
        {"type": "handoff", "task": task, "message": message}
    )
    assert task in payload
    assert message in payload


@SETTINGS
@given(message=TEXT)
def test_note_payload_is_the_message_alone(message):
    payload = mailbox.build_payload({"type": "note", "task": None, "message": message})
    assert payload == message


@SETTINGS
@given(stamp=st.sampled_from([None, "", "not-a-stamp"]))
def test_age_seconds_of_an_absent_or_bad_stamp_is_none(stamp):
    assert mailbox.age_seconds(stamp) is None


def test_age_helpers_mark_an_absent_stamp():
    assert mailbox.format_age(None) == "-"
    assert mailbox.age_seconds(mailbox.iso_now()) >= 0


OWNER = st.one_of(st.none(), st.from_regex(r"[a-z][a-z0-9-]{0,6}", fullmatch=True))
SESSION = st.one_of(st.none(), st.from_regex(r"[a-z][a-z0-9-]{0,6}", fullmatch=True))


def _write_item(directory, name, owner):
    path = directory / name
    path.write_text(json.dumps({"id": name, "owner_session": owner}))
    return path


@FIXTURE_SETTINGS
@given(owner=OWNER, session=SESSION)
def test_check_owners_admits_only_the_owner(tmp_path, owner, session):
    item = _write_item(tmp_path, "item.json", owner)
    args = SimpleNamespace(session=session, takeover=False)
    if owner is not None and session != owner:
        with pytest.raises(mailbox.MailError) as refusal:
            mailbox._check_owners("coder", [item], args)
        assert f"owned by session {owner}" in str(refusal.value)
    else:
        mailbox._check_owners("coder", [item], args)


@FIXTURE_SETTINGS
@given(owners=st.lists(OWNER, min_size=2, max_size=4, unique=True))
def test_check_owners_refuses_mixed_ownership(tmp_path, owners):
    assume(sum(owner is not None for owner in owners) > 1)
    items = [_write_item(tmp_path, f"item{index}.json", owner) for index, owner in enumerate(owners)]
    args = SimpleNamespace(session=None, takeover=False)
    with pytest.raises(mailbox.MailError) as refusal:
        mailbox._check_owners("coder", items, args)
    assert "mixed ownership" in str(refusal.value)


# A valid JSON document can never be followed by a stray `{`, so the suffix
# guarantees the file is malformed regardless of the generated prefix.
MALFORMED_JSON = st.text(min_size=1, max_size=40).map(lambda text: text + "{")


@FIXTURE_SETTINGS
@given(text=MALFORMED_JSON)
def test_read_item_fails_closed_on_malformed_json(tmp_path, text):
    path = tmp_path / "50_item.json"
    path.write_text(text)
    with pytest.raises(mailbox.MailError) as refusal:
        mailbox.read_item(path)
    assert "corrupt" in str(refusal.value)
    assert path.read_bytes() == text.encode()


@FIXTURE_SETTINGS
@given(name=st.from_regex(r"[a-z][a-z0-9-]{0,8}\.json", fullmatch=True))
def test_read_item_fails_closed_on_a_missing_file(tmp_path, name):
    with pytest.raises(mailbox.MailError) as refusal:
        mailbox.read_item(tmp_path / name)
    assert "corrupt" in str(refusal.value)


@FIXTURE_SETTINGS
@given(
    digest=st.text(min_size=1, max_size=20),
    item_id=st.text(min_size=1, max_size=20),
    folder=st.sampled_from(["new", "in_process", "completed"]),
)
def test_find_active_only_sees_new_and_in_process(
    tmp_path, monkeypatch, digest, item_id, folder
):
    """A completed item is never re-claimed as an active handoff."""
    state = tmp_path / "state"
    shutil.rmtree(state, ignore_errors=True)
    monkeypatch.setattr(mailbox, "_STATE_ROOT_OVERRIDE", state)
    for name in ("new", "in_process", "completed"):
        (state / "mail" / "inbox" / "coder" / name).mkdir(parents=True, exist_ok=True)
    (state / "mail" / "inbox" / "coder" / folder / "item.json").write_text(
        json.dumps({"id": item_id, "content_hash": digest})
    )
    found = mailbox.find_active(tmp_path / "project", "coder", digest)
    assert found == (item_id if folder in ("new", "in_process") else None)
