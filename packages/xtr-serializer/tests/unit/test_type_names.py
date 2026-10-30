"""A class's names, read without running its metaclass."""

from __future__ import annotations

from tests.fixtures.nameless import NamelessThing, names_refused
from xtr_serializer._type_names import name_of, qualified_name_of


class Outer:
    """A class holding another, whose qualified name differs from its name."""

    class Inner:
        """A class held by another."""


def test_it_gives_a_class_its_name_and_qualified_name() -> None:
    assert (name_of(Outer.Inner), qualified_name_of(Outer.Inner)) == ("Inner", "Outer.Inner")


def test_it_reads_the_names_past_a_metaclass_that_refuses_them() -> None:
    with names_refused():
        names = (name_of(NamelessThing), qualified_name_of(NamelessThing))

    assert names == ("NamelessThing", "NamelessThing")
