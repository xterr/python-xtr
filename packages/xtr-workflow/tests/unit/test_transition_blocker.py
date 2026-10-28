"""A transition blocker says why a transition cannot be applied, in words and as a code."""

from __future__ import annotations

from typing import final

from xtr_workflow import Marking, TransitionBlocker

UNKNOWN_CODE = "e8b5bbb9-5913-4b98-bfa6-65dbd228a82a"


def _block() -> TransitionBlocker:
    """Stands where a guard event's set_blocked stands: between the guard and the factory."""
    return TransitionBlocker.create_unknown()


@final
class _Guard:
    def block(self) -> TransitionBlocker:
        return _block()

    @classmethod
    def block_from_class(cls) -> TransitionBlocker:
        return _block()

    def block_here(self) -> TransitionBlocker:
        return TransitionBlocker.create_unknown(backtrace_frame=1)


def test_it_keeps_its_message_code_and_parameters() -> None:
    blocker = TransitionBlocker("Too far.", "distance", {"miles": 5})

    assert blocker.get_message() == "Too far."
    assert blocker.get_code() == "distance"
    assert blocker.get_parameters() == {"miles": 5}


def test_its_parameters_are_empty_unless_given() -> None:
    assert TransitionBlocker("Too far.", "distance").get_parameters() == {}


def test_changing_the_parameters_it_returns_leaves_it_unchanged() -> None:
    blocker = TransitionBlocker("Too far.", "distance", {"miles": 5})

    blocker.get_parameters()["miles"] = 6

    assert blocker.get_parameters() == {"miles": 5}


def test_its_codes_are_the_ones_every_reader_knows() -> None:
    assert TransitionBlocker.BLOCKED_BY_MARKING == "19beefc8-6b1e-4716-9d07-a39bd6d16e34"
    assert (
        TransitionBlocker.BLOCKED_BY_EXPRESSION_GUARD_LISTENER
        == "326a1e9c-0c12-11e8-ba89-0ed5f89f718b"
    )
    assert TransitionBlocker.UNKNOWN == UNKNOWN_CODE


def test_a_marking_that_does_not_enable_the_transition_blocks_it() -> None:
    marking = Marking({"a": 1})

    blocker = TransitionBlocker.create_blocked_by_marking(marking)

    assert blocker.get_message() == "The marking does not enable the transition."
    assert blocker.get_code() == TransitionBlocker.BLOCKED_BY_MARKING
    assert blocker.get_parameters() == {"marking": marking}


def test_a_guard_expression_blocks_it() -> None:
    blocker = TransitionBlocker.create_blocked_by_expression_guard_listener("is_admin")

    assert blocker.get_message() == "The expression blocks the transition."
    assert blocker.get_code() == TransitionBlocker.BLOCKED_BY_EXPRESSION_GUARD_LISTENER
    assert blocker.get_parameters() == {"expression": "is_admin"}


def test_an_unknown_reason_given_a_message_reads_as_it() -> None:
    blocker = TransitionBlocker.create_unknown("You should not pass !!")

    assert blocker.get_message() == "You should not pass !!"
    assert blocker.get_code() == UNKNOWN_CODE
    assert blocker.get_parameters() == {}


def test_an_unknown_reason_names_the_class_of_the_guard_that_blocked() -> None:
    blocker = _Guard().block()

    assert blocker.get_message() == (
        "The transition has been blocked by a guard (tests.unit.test_transition_blocker._Guard)."
    )
    assert blocker.get_code() == UNKNOWN_CODE


def test_an_unknown_reason_names_the_class_a_class_method_guard_belongs_to() -> None:
    blocker = _Guard.block_from_class()

    assert blocker.get_message() == (
        "The transition has been blocked by a guard (tests.unit.test_transition_blocker._Guard)."
    )


def test_an_unknown_reason_from_a_guard_outside_a_class_names_none() -> None:
    def guard() -> TransitionBlocker:
        return _block()

    assert guard().get_message() == "The transition has been blocked by a guard."


def test_the_frame_the_guard_is_read_from_can_be_chosen() -> None:
    blocker = _Guard().block_here()

    assert blocker.get_message() == (
        "The transition has been blocked by a guard (tests.unit.test_transition_blocker._Guard)."
    )


def test_a_frame_beyond_the_stack_names_no_guard() -> None:
    blocker = TransitionBlocker.create_unknown(backtrace_frame=100_000)

    assert blocker.get_message() == "The transition has been blocked by a guard."
