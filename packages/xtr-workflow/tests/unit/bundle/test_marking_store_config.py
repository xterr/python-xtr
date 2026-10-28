"""A marking store's configuration names a method store, its property, or a store service."""

from __future__ import annotations

from typing import Literal, cast

import pytest

from xtr_workflow.bundle import MarkingStoreConfig
from xtr_workflow.exception import InvalidArgumentError


def test_nothing_is_set_by_default() -> None:
    store = MarkingStoreConfig()

    assert store.type is None
    assert store.property is None
    assert store.service is None


def test_the_method_store_and_its_property_can_be_named() -> None:
    store = MarkingStoreConfig(type="method", property="status")

    assert store.type == "method"
    assert store.property == "status"


def test_a_type_other_than_method_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = MarkingStoreConfig(type=cast("Literal['method']", cast("object", "single_state")))

    assert str(raised.value) == (
        'The value "single_state" is not allowed for the marking store type. '
        'Permissible values: "method".'
    )


def test_an_empty_property_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = MarkingStoreConfig(property="")

    assert str(raised.value) == (
        'The marking store property cannot contain an empty value, but got "".'
    )


def test_an_empty_service_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = MarkingStoreConfig(service="")

    assert (
        str(raised.value) == 'The marking store service cannot contain an empty value, but got "".'
    )
