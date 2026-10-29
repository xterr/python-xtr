"""Unit tests for :class:`xtr_maker.ClassName`."""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from xtr_maker import ClassName, InvalidClassNameError


def _create(name: str, *, kind: str = "message", suffix: str = "") -> ClassName:
    return ClassName.create(name, root_package="app", kind=kind, suffix=suffix)


@pytest.mark.parametrize("typed", ["place order", "PlaceOrder", "place_order", " place-order "])
def test_a_typed_name_becomes_the_class_its_module_and_its_file(typed: str) -> None:
    name = _create(typed)

    assert name.short_name == "PlaceOrder"
    assert name.module == "app.message.place_order"
    assert name.path == PurePosixPath("message/place_order.py")


@pytest.mark.parametrize(
    "typed", ["ordering.PlaceOrder", "Ordering.PlaceOrder", "ordering/place order"]
)
def test_a_dotted_name_puts_the_class_in_a_subpackage_of_its_kind(typed: str) -> None:
    name = _create(typed)

    assert name.package == ("message", "ordering")
    assert name.package_name == "app.message.ordering"
    assert name.module == "app.message.ordering.place_order"
    assert name.path == PurePosixPath("message/ordering/place_order.py")


def test_a_nested_kind_is_a_folder_per_part() -> None:
    name = _create("owner", kind="security.voter", suffix="Voter")

    assert name.path == PurePosixPath("security/voter/owner_voter.py")


def test_the_suffix_is_added() -> None:
    name = _create("place order", kind="message_handler", suffix="Handler")

    assert name.short_name == "PlaceOrderHandler"
    assert name.snake_name == "place_order_handler"
    assert name.module == "app.message_handler.place_order_handler"


def test_the_suffix_is_not_doubled() -> None:
    name = _create("PlaceOrderHandler", kind="message_handler", suffix="Handler")

    assert name.short_name == "PlaceOrderHandler"


def test_name_without_suffix_drops_the_suffix() -> None:
    name = _create("place order", kind="message_handler", suffix="Handler")

    assert name.name_without_suffix == "PlaceOrder"


def test_name_without_suffix_keeps_a_name_that_is_only_the_suffix() -> None:
    name = ClassName(
        root_package="app", package=("message_handler",), short_name="Handler", suffix="Handler"
    )

    assert name.name_without_suffix == "Handler"


def test_a_dotted_root_package_prefixes_the_module() -> None:
    name = ClassName.create("place order", root_package="acme.shop", kind="message")

    assert name.module == "acme.shop.message.place_order"


@pytest.mark.parametrize("typed", ["", "   ", "place order!", "ordering..", "café"])
def test_a_name_with_nothing_usable_is_refused(typed: str) -> None:
    with pytest.raises(InvalidClassNameError):
        _ = _create(typed)


def test_a_name_starting_with_a_digit_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="not a Python identifier"):
        _ = _create("2fa token")


def test_a_keyword_class_name_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="keyword"):
        _ = _create("none")


def test_a_class_named_after_a_builtin_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="builtin"):
        _ = _create("value error")


def test_a_class_whose_module_would_be_a_keyword_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="module 'import' is a Python keyword"):
        _ = _create("Import")


def test_a_keyword_subpackage_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="module 'class' is a Python keyword"):
        _ = _create("class.Order")


def test_a_root_package_that_is_not_an_identifier_is_refused() -> None:
    with pytest.raises(InvalidClassNameError, match="module 'my-app' is not a Python identifier"):
        _ = ClassName.create("order", root_package="my-app", kind="message")


def test_a_refused_name_carries_what_was_typed_and_why() -> None:
    with pytest.raises(InvalidClassNameError) as raised:
        _ = _create("none")

    assert raised.value.name == "None"
    assert raised.value.reason == "it is a Python keyword"
