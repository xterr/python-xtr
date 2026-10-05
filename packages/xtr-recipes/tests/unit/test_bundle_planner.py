from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from xtr_recipes.bundle_entry import BundleEntry
from xtr_recipes.bundle_planner import BundlePlanner
from xtr_recipes.bundle_requirements import BundleRequirements
from xtr_recipes.bundles_file import BundlesFile

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle


@final
@as_bundle("planner_clock")
class ClockBundle(Bundle):
    pass


@final
@required_bundle(ClockBundle)
@as_bundle("planner_logging")
class LoggingBundle(Bundle):
    pass


@final
@as_bundle("planner_messenger")
class MessengerBundle(Bundle):
    pass


_CLOCK = "xtr_clock.bundle:ClockBundle"
_LOGGING = "xtr_logging.bundle:LoggingBundle"
_MESSENGER = "xtr_messenger.bundle:MessengerBundle"
_ALL = {"all": True}
_KNOWN: Mapping[str, type[AnyBundle]] = {
    _CLOCK: ClockBundle,
    _LOGGING: LoggingBundle,
    _MESSENGER: MessengerBundle,
}


def _loader() -> Callable[[str], type[AnyBundle] | None]:
    def load(target: str) -> type[AnyBundle] | None:
        return _KNOWN.get(target)

    return load


def _planner() -> BundlePlanner:
    return BundlePlanner(BundleRequirements(_loader()))


def _file(*targets: str) -> BundlesFile:
    return BundlesFile(entries=tuple(BundleEntry(target=target, flags=_ALL) for target in targets))


def test_a_candidate_nothing_requires_is_listed() -> None:
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


def test_a_candidate_another_candidate_requires_is_left_out() -> None:
    new_file, states = _planner().finalize(_file(), set(), {_LOGGING: _ALL, _CLOCK: _ALL})

    assert states == {_LOGGING: "listed", _CLOCK: "required"}
    assert [entry.target for entry in new_file.entries] == [_LOGGING]


def test_a_candidate_an_already_listed_bundle_requires_is_left_out() -> None:
    _, states = _planner().finalize(_file(_LOGGING), set(), {_CLOCK: _ALL})

    assert states == {_CLOCK: "required"}


def test_a_candidate_is_listed_once_its_requirer_is_removed() -> None:
    new_file, states = _planner().finalize(_file(_LOGGING), {_LOGGING}, {_CLOCK: _ALL})

    assert states == {_CLOCK: "listed"}
    assert [entry.target for entry in new_file.entries] == [_CLOCK]


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
