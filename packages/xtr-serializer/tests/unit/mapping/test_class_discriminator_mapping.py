"""The names a class of a hierarchy is read by, and the classes they stand for."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass

import pytest

from tests.fixtures.hierarchies import (
    Batch,
    Bounce,
    Complaint,
    Delivery,
    Event,
    Failure,
    Mailbox,
    Unnamed,
)
from xtr_serializer import ClassDiscriminatorMapping, discriminator_map, discriminator_name


def test_the_base_maps_every_name_of_its_hierarchy() -> None:
    mapping = ClassDiscriminatorMapping.for_class(Event)

    assert mapping == ClassDiscriminatorMapping(
        "$type",
        {
            "event": Event,
            "delivery": Delivery,
            "bounce": Bounce,
            "complaint": Complaint,
            "batch": Batch,
        },
    )


def test_a_class_inside_maps_the_names_its_fields_take() -> None:
    assert ClassDiscriminatorMapping.for_class(Failure) == ClassDiscriminatorMapping(
        "$type", {"bounce": Bounce, "complaint": Complaint}
    )
    assert ClassDiscriminatorMapping.for_class(Unnamed) == ClassDiscriminatorMapping("$type", {})


def test_a_class_outside_every_hierarchy_has_none() -> None:
    assert ClassDiscriminatorMapping.for_class(Mailbox) is None
    assert ClassDiscriminatorMapping.for_class(int) is None


def test_the_mapping_cannot_be_changed() -> None:
    mapping = ClassDiscriminatorMapping.for_class(Event)
    assert mapping is not None

    with pytest.raises(TypeError):
        # Changing it is what the type checkers rightly refuse, and what is tried here.
        mapping.types_mapping["forged"] = Event  # pyright: ignore[reportIndexIssue]  # ty: ignore[invalid-assignment]
    with pytest.raises(FrozenInstanceError):
        mapping.type_property = "kind"  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_a_mapping_is_a_copy_that_names_registered_later_leave_as_it_was() -> None:
    @discriminator_name("base")
    @discriminator_map()
    @dataclass
    class Base:
        pass

    mapping = ClassDiscriminatorMapping.for_class(Base)
    _ = discriminator_name("sub")(type("Sub", (Base,), {}))

    assert mapping == ClassDiscriminatorMapping("$type", {"base": Base})


def test_equal_mappings_hash_alike() -> None:
    mapping = ClassDiscriminatorMapping("$type", {"bounce": Bounce, "complaint": Complaint})
    reordered = ClassDiscriminatorMapping("$type", {"complaint": Complaint, "bounce": Bounce})

    assert hash(mapping) == hash(reordered)
    assert {mapping, reordered} == {ClassDiscriminatorMapping.for_class(Failure)}
