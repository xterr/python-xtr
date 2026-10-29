"""Unit tests for :class:`xtr_maker.NameConverter`."""

from __future__ import annotations

import pytest

from xtr_maker import NameConverter


@pytest.mark.parametrize(
    ("typed", "words"),
    [
        ("place order", ("place", "order")),
        ("PlaceOrder", ("Place", "Order")),
        ("place_order", ("place", "order")),
        ("place-order", ("place", "order")),
        ("HTTPClient", ("HTTP", "Client")),
        ("order2 item", ("order2", "item")),
    ],
)
def test_words_split_at_separators_and_case_changes(typed: str, words: tuple[str, ...]) -> None:
    assert NameConverter.words(typed) == words


@pytest.mark.parametrize(
    ("typed", "class_name"),
    [
        ("place order", "PlaceOrder"),
        ("place_order", "PlaceOrder"),
        ("place-order", "PlaceOrder"),
        ("placeOrder", "PlaceOrder"),
        ("PlaceOrder", "PlaceOrder"),
    ],
)
def test_as_class_name_joins_capitalised_words(typed: str, class_name: str) -> None:
    assert NameConverter.as_class_name(typed) == class_name


def test_as_class_name_keeps_a_class_name_as_typed() -> None:
    assert NameConverter.as_class_name("HTTPClient") == "HTTPClient"


@pytest.mark.parametrize(
    ("typed", "snake"),
    [
        ("PlaceOrder", "place_order"),
        ("HTTPClient", "http_client"),
        ("place order", "place_order"),
        ("place-order", "place_order"),
    ],
)
def test_as_snake_case_lowercases_and_joins_with_underscores(typed: str, snake: str) -> None:
    assert NameConverter.as_snake_case(typed) == snake


def test_as_kebab_case_lowercases_and_joins_with_dashes() -> None:
    assert NameConverter.as_kebab_case("SendReport") == "send-report"


@pytest.mark.parametrize(
    ("singular", "plural"),
    [
        ("book", "books"),
        ("category", "categories"),
        ("day", "days"),
        ("status", "statuses"),
        ("box", "boxes"),
        ("batch", "batches"),
        ("address", "addresses"),
        ("analysis", "analyses"),
        ("person", "people"),
        ("child", "children"),
        ("data", "data"),
        ("database", "databases"),
        ("house", "houses"),
    ],
)
def test_pluralize_and_singularize_are_inverse(singular: str, plural: str) -> None:
    assert NameConverter.pluralize(singular) == plural
    assert NameConverter.singularize(plural) == singular


def test_pluralize_changes_only_the_last_word_keeping_its_case() -> None:
    assert NameConverter.pluralize("OrderItem") == "OrderItems"
    assert NameConverter.pluralize("order_category") == "order_categories"
    assert NameConverter.pluralize("ORDER_PERSON") == "ORDER_PEOPLE"


def test_pluralize_leaves_a_plural_alone() -> None:
    assert NameConverter.pluralize("people") == "people"


def test_singularize_leaves_a_singular_ending_in_s_alone() -> None:
    assert NameConverter.singularize("class") == "class"
    assert NameConverter.singularize("status") == "status"


def test_a_name_without_a_trailing_word_is_unchanged() -> None:
    assert NameConverter.pluralize("v2") == "v2"


def test_as_table_name_is_plural_and_snake_cased() -> None:
    assert NameConverter.as_table_name("OrderItem") == "order_items"
