"""The identifier trait names an entity, and its reading cuts the name short."""

from __future__ import annotations

import pytest

from tests.support.entities import Scope

_LONG = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def test_it_hands_back_the_identifier_it_was_given() -> None:
    entity = Scope()
    entity.set_identifier("read")

    assert entity.get_identifier() == "read"


def test_reading_an_identifier_nobody_set_refuses() -> None:
    with pytest.raises(AttributeError):
        _ = Scope().get_identifier()


def test_its_reading_cuts_a_long_identifier_short() -> None:
    entity = Scope()
    entity.set_identifier(_LONG)

    assert repr(entity) == "Scope(identifier='a1b2c3d4...')"


def test_its_reading_holds_a_short_identifier_whole() -> None:
    entity = Scope()
    entity.set_identifier("read")

    assert repr(entity) == "Scope(identifier='read')"


def test_its_reading_says_so_when_no_identifier_was_set() -> None:
    assert repr(Scope()) == "Scope(identifier=unset)"
