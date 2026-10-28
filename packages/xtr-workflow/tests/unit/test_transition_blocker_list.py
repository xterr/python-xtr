"""A transition blocker list holds every reason a transition is blocked, in the order given."""

from __future__ import annotations

from xtr_workflow import TransitionBlocker, TransitionBlockerList

FIRST = TransitionBlocker("Transition blocker 1", "blocker_1")
SECOND = TransitionBlocker("Transition blocker 2", "blocker_2")


def test_it_is_empty_unless_given_blockers() -> None:
    blockers = TransitionBlockerList()

    assert blockers.is_empty()
    assert len(blockers) == 0
    assert list(blockers) == []


def test_it_holds_the_blockers_it_is_built_with_in_order() -> None:
    blockers = TransitionBlockerList([FIRST, SECOND])

    assert not blockers.is_empty()
    assert len(blockers) == 2
    assert list(blockers) == [FIRST, SECOND]


def test_adding_a_blocker_puts_it_last() -> None:
    blockers = TransitionBlockerList([FIRST])

    blockers.add(SECOND)

    assert list(blockers) == [FIRST, SECOND]


def test_it_tells_whether_a_blocker_has_a_code() -> None:
    blockers = TransitionBlockerList([FIRST])

    assert blockers.has("blocker_1")
    assert not blockers.has("blocker_2")


def test_clearing_it_forgets_every_blocker() -> None:
    blockers = TransitionBlockerList([FIRST, SECOND])

    blockers.clear()

    assert blockers.is_empty()
    assert not blockers.has("blocker_1")


def test_adding_while_iterating_leaves_the_iteration_unchanged() -> None:
    blockers = TransitionBlockerList([FIRST])

    seen: list[TransitionBlocker] = []
    for blocker in blockers:
        seen.append(blocker)
        blockers.add(SECOND)

    assert seen == [FIRST]
    assert len(blockers) == 2
