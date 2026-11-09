"""Naming a class in a session, and finding it again among the classes already loaded."""

from __future__ import annotations

import sys

from xtr_security_http.session._session_kinds import kind_of, loaded_kind


class _Root:
    """The root a lookup walks from."""


class _Child(_Root):
    """A subclass of the root."""


class _Grandchild(_Child):
    """A subclass of a subclass of the root."""


def test_a_kind_is_the_module_and_the_qualified_name() -> None:
    assert kind_of(_Grandchild) == f"{__name__}:_Grandchild"


def test_a_loaded_subclass_is_found_by_its_kind_however_deep() -> None:
    assert loaded_kind(_Root, kind_of(_Child)) is _Child
    assert loaded_kind(_Root, kind_of(_Grandchild)) is _Grandchild


def test_the_root_itself_is_no_kind_of_its_own() -> None:
    assert loaded_kind(_Root, kind_of(_Root)) is None


def test_a_class_outside_the_root_is_not_found() -> None:
    assert loaded_kind(_Child, kind_of(_Root)) is None


def test_a_kind_shared_by_two_loaded_classes_answers_the_one_made_last() -> None:
    first = type("_Twin", (_Root,), {"__module__": __name__, "__qualname__": "_Twin"})
    last = type("_Twin", (_Root,), {"__module__": __name__, "__qualname__": "_Twin"})

    assert first is not last
    assert loaded_kind(_Root, kind_of(last)) is last


def test_a_kind_naming_a_module_nobody_loaded_names_nothing_and_loads_nothing() -> None:
    assert loaded_kind(_Root, "xtr_never_loaded_module:Thing") is None
    assert "xtr_never_loaded_module" not in sys.modules
