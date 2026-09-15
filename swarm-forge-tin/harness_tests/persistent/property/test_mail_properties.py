"""Property tests for the mail tool's content-identity (dedup) invariant."""

import mailbox
import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

TEXT = st.text(alphabet=string.ascii_lowercase + " /._-", min_size=1, max_size=20)
SETTINGS = settings(max_examples=50, deadline=None)


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
