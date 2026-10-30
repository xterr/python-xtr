"""Each hierarchy's names, and the classes a schema was built for, kept apart from the others."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from xtr_serializer import MappingError
from xtr_serializer.mapping._class_discriminator_registry import (
    ClassDiscriminatorRegistry,
    Members,
)


@dataclass
class Root:
    pass


@dataclass
class Middle(Root):
    pass


@dataclass
class Leaf(Middle):
    pass


@dataclass
class Other:
    pass


def registry() -> ClassDiscriminatorRegistry:
    registry = ClassDiscriminatorRegistry()
    registry.add_hierarchy(Root, "kind")
    return registry


def test_a_class_is_in_the_hierarchy_of_its_base() -> None:
    names = registry()

    assert (names.is_root(Root), names.is_root(Leaf)) == (True, False)
    assert (names.in_hierarchy(Leaf), names.in_hierarchy(Other)) == (True, False)
    assert (names.type_property_of(Leaf), names.type_property_of(Other)) == ("kind", None)


def test_a_class_takes_the_named_classes_under_it_in_the_order_they_were_named() -> None:
    names = registry()
    names.register(Leaf, "leaf")
    names.register(Root, "root")

    assert names.members(Root) == Members("kind", (("leaf", Leaf), ("root", Root)))
    assert names.members(Middle) == Members("kind", (("leaf", Leaf),))
    assert names.members(Other) is None


def test_claiming_names_keeps_later_names_out_of_the_classes_claimed_only() -> None:
    names = registry()
    names.register(Leaf, "leaf")

    assert names.claim(Middle, even_unnamed=False) == Members("kind", (("leaf", Leaf),))
    names.register(Root, "root")
    with pytest.raises(MappingError, match="before"):
        names.register(type("Late", (Middle,), {}), "late")


def test_claiming_no_names_keeps_nothing_out_unless_asked_to() -> None:
    names = registry()

    assert names.claim(Middle, even_unnamed=False) == Members("kind", ())
    names.register(Leaf, "leaf")
    assert names.claim(Root, even_unnamed=True) == Members("kind", (("leaf", Leaf),))
    assert names.claim(Other, even_unnamed=True) is None


def test_claiming_no_names_when_asked_to_keeps_later_names_out() -> None:
    names = registry()

    assert names.claim(Middle, even_unnamed=True) == Members("kind", ())
    with pytest.raises(MappingError, match="before"):
        names.register(Leaf, "leaf")
