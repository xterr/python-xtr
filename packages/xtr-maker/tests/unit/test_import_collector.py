"""Unit tests for :class:`xtr_maker.ImportCollector`.

The expected strings are what the linter's import sorting and the formatter
write with their defaults, checked against them when written.
"""

from __future__ import annotations

from xtr_maker import ImportCollector


def test_nothing_added_renders_nothing() -> None:
    assert ImportCollector("app").render() == ""


def test_imports_are_grouped_standard_library_third_party_then_the_application() -> None:
    imports = ImportCollector("app")
    _ = imports.add("app.message.place_order", "PlaceOrder")
    _ = imports.add("xtr_messenger", "as_message_handler")
    _ = imports.add("typing", "final")
    _ = imports.add("dataclasses", "dataclass")

    assert imports.render() == (
        "from dataclasses import dataclass\n"
        "from typing import final\n"
        "\n"
        "from xtr_messenger import as_message_handler\n"
        "\n"
        "from app.message.place_order import PlaceOrder"
    )


def test_names_of_one_module_share_a_statement_constants_then_classes_then_the_rest() -> None:
    imports = ImportCollector("app")
    for name in ("final", "TYPE_CHECKING", "Final", "item10", "item2", "T"):
        _ = imports.add("typing", name)

    assert imports.render() == "from typing import TYPE_CHECKING, Final, T, final, item2, item10"


def test_modules_are_sorted_with_a_package_before_its_submodules() -> None:
    imports = ImportCollector("app")
    _ = imports.add("xtr_dependency_injection_x", "Q")
    _ = imports.add("xtr_dependency_injection.kernel", "KernelInterface")
    _ = imports.add("xtr_dependency_injection", "Injected")

    assert imports.render() == (
        "from xtr_dependency_injection import Injected\n"
        "from xtr_dependency_injection.kernel import KernelInterface\n"
        "from xtr_dependency_injection_x import Q"
    )


def test_a_name_held_by_another_module_is_aliased_on_its_own_statement() -> None:
    imports = ImportCollector("app")
    first = imports.add("xtr_event_dispatcher", "Event")
    second = imports.add("xtr_messenger.event", "Event")
    _ = imports.add("xtr_messenger.event", "Envelope")

    assert (first, second) == ("Event", "XtrMessengerEvent")
    assert imports.render() == (
        "from xtr_event_dispatcher import Event\n"
        "from xtr_messenger.event import Envelope\n"
        "from xtr_messenger.event import Event as XtrMessengerEvent"
    )


def test_an_alias_already_taken_gets_a_number() -> None:
    imports = ImportCollector("app")
    _ = imports.add("a.event", "Event")
    _ = imports.add("b.event", "Event")

    assert imports.add("b.event.event", "Event") == "BEvent2"


def test_a_lowercase_name_is_aliased_in_snake_case() -> None:
    imports = ImportCollector("app")
    _ = imports.add("a", "configure")

    assert imports.add("b.bundle_config", "configure") == "bundle_config_configure"


def test_adding_a_name_twice_returns_the_same_name() -> None:
    imports = ImportCollector("app")
    _ = imports.add("xtr_messenger.event", "Event")

    assert imports.add("xtr_messenger.event", "Event") == "Event"
    assert imports.render() == "from xtr_messenger.event import Event"


def test_annotation_only_names_go_in_a_type_checking_block() -> None:
    imports = ImportCollector("app")
    _ = imports.add("typing", "final")
    _ = imports.add("app.entity.book", "Book", type_checking=True)
    _ = imports.add("collections.abc", "Sequence", type_checking=True)
    _ = imports.add("xtr_orm", "Thing", type_checking=True)

    assert imports.render() == (
        "from typing import TYPE_CHECKING, final\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from collections.abc import Sequence\n"
        "\n"
        "    from xtr_orm import Thing\n"
        "\n"
        "    from app.entity.book import Book"
    )


def test_a_name_also_used_at_runtime_is_imported_at_runtime() -> None:
    imports = ImportCollector("app")
    _ = imports.add("app.entity.book", "Book", type_checking=True)
    _ = imports.add("app.entity.book", "Book")

    assert imports.render() == "from app.entity.book import Book"


def test_type_checking_added_by_hand_is_not_imported_twice() -> None:
    imports = ImportCollector("app")
    _ = imports.add("typing", "TYPE_CHECKING")
    _ = imports.add("app.entity.book", "Book", type_checking=True)

    assert imports.render().startswith("from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:")


def test_a_statement_too_long_for_a_line_is_wrapped_one_name_per_line() -> None:
    imports = ImportCollector("app")
    for name in ("Other", "PlaceOrderWithARatherLongName", "ThirdOne"):
        _ = imports.add("app.message.ordering.place_order_with_a_rather_long_name", name)

    assert imports.render() == (
        "from app.message.ordering.place_order_with_a_rather_long_name import (\n"
        "    Other,\n"
        "    PlaceOrderWithARatherLongName,\n"
        "    ThirdOne,\n"
        ")"
    )


def test_a_wrapped_statement_in_the_type_checking_block_is_indented_with_it() -> None:
    imports = ImportCollector("app", line_length=40)
    _ = imports.add("app.entity.book", "Book", type_checking=True)
    _ = imports.add("app.entity.book", "Author", type_checking=True)

    assert imports.render().endswith(
        "if TYPE_CHECKING:\n"
        "    from app.entity.book import (\n"
        "        Author,\n"
        "        Book,\n"
        "    )"
    )


def test_the_first_party_package_is_the_top_level_of_a_dotted_root() -> None:
    imports = ImportCollector("acme.shop")
    _ = imports.add("acme.billing", "Invoice")
    _ = imports.add("attrs", "define")

    assert imports.render() == "from attrs import define\n\nfrom acme.billing import Invoice"
