from __future__ import annotations

from xtr_recipes.bundle_entry import BundleEntry
from xtr_recipes.bundle_planner import BundlePlanner
from xtr_recipes.bundles_file import BundlesFile

_CLOCK = "xtr_clock.bundle:ClockBundle"
_LOGGING = "xtr_logging.bundle:LoggingBundle"
_MESSENGER = "xtr_messenger.bundle:MessengerBundle"
_ALL = {"all": True}


def _planner() -> BundlePlanner:
    return BundlePlanner()


def _file(*targets: str) -> BundlesFile:
    return BundlesFile(entries=tuple(BundleEntry(target=target, flags=_ALL) for target in targets))


def test_a_candidate_is_listed() -> None:
    new_file, states = _planner().finalize(_file(), set(), {_MESSENGER: _ALL})

    assert states == {_MESSENGER: "listed"}
    assert [entry.target for entry in new_file.entries] == [_MESSENGER]


def test_a_candidate_already_listed_is_adopted_and_not_listed_twice() -> None:
    new_file, states = _planner().finalize(_file(_MESSENGER), set(), {_MESSENGER: _ALL})

    assert states == {_MESSENGER: "adopted"}
    assert [entry.target for entry in new_file.entries] == [_MESSENGER]


def test_an_adopted_candidate_keeps_the_environments_it_was_listed_with() -> None:
    existing = BundlesFile(entries=(BundleEntry(target=_MESSENGER, flags={"dev": True}),))

    new_file, _ = _planner().finalize(existing, set(), {_MESSENGER: _ALL})

    assert new_file.entries[0].flags == {"dev": True}


def test_a_candidate_another_candidate_requires_is_listed_too() -> None:
    new_file, states = _planner().finalize(_file(), set(), {_LOGGING: _ALL, _CLOCK: _ALL})

    assert states == {_LOGGING: "listed", _CLOCK: "listed"}
    assert [entry.target for entry in new_file.entries] == [_LOGGING, _CLOCK]


def test_a_removed_target_leaves_the_list() -> None:
    new_file, _ = _planner().finalize(_file(_MESSENGER, _CLOCK), {_MESSENGER}, {})

    assert [entry.target for entry in new_file.entries] == [_CLOCK]


def test_listing_follows_the_order_the_candidates_were_named() -> None:
    new_file, _ = _planner().finalize(_file(), set(), {_MESSENGER: _ALL, _CLOCK: _ALL})

    assert [entry.target for entry in new_file.entries] == [_MESSENGER, _CLOCK]


def test_a_plan_with_no_candidates_reports_no_states() -> None:
    new_file, states = _planner().finalize(_file(_MESSENGER), set(), {})

    assert states == {}
    assert [entry.target for entry in new_file.entries] == [_MESSENGER]
