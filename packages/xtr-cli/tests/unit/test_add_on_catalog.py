from __future__ import annotations

import pytest

from xtr_cli import AddOnCatalog, UnknownAddOnError


@pytest.fixture
def catalog() -> AddOnCatalog:
    return AddOnCatalog.default()


def test_a_name_alone_takes_the_default_variants(catalog: AddOnCatalog) -> None:
    (orm,) = catalog.parse("orm", "cli")

    assert orm.requirement == "xtr-orm[sqlite]"


def test_variants_are_kept_in_the_order_the_add_on_lists_them(catalog: AddOnCatalog) -> None:
    (orm,) = catalog.parse("orm:postgres+sqlite", "cli")

    assert orm.variants == ("sqlite", "postgres")


def test_a_colon_with_nothing_after_it_picks_no_variant(catalog: AddOnCatalog) -> None:
    (orm,) = catalog.parse("orm:", "cli")

    assert orm.variants == ()


def test_several_add_ons_are_read_in_the_order_written(catalog: AddOnCatalog) -> None:
    chosen = catalog.parse(" messenger , orm ,, lock ", "cli")

    assert [choice.add_on.name for choice in chosen] == ["messenger", "orm", "lock"]


def test_an_empty_value_chooses_nothing(catalog: AddOnCatalog) -> None:
    assert catalog.parse("", "cli") == ()


def test_an_unknown_add_on_names_what_could_be_chosen(catalog: AddOnCatalog) -> None:
    with pytest.raises(UnknownAddOnError, match="can take orm, messenger"):
        _ = catalog.parse("queue", "cli")


def test_an_add_on_the_template_cannot_take_is_refused(catalog: AddOnCatalog) -> None:
    with pytest.raises(UnknownAddOnError, match="a cli project"):
        _ = catalog.parse("security", "cli")


@pytest.mark.parametrize("name", ["security", "jwt", "oauth2", "webhook"])
def test_only_the_web_template_takes_the_web_add_ons(catalog: AddOnCatalog, name: str) -> None:
    assert name in [add_on.name for add_on in catalog.available("webapp")]
    assert name not in [add_on.name for add_on in catalog.available("cli")]


@pytest.mark.parametrize(
    ("text", "requirement"),
    [
        ("http-client", "xtr-http-client"),
        ("http-client:http2", "xtr-http-client[http2]"),
        ("oauth2", "xtr-security-oauth2-server"),
        ("webhook", "xtr-webhook"),
    ],
)
def test_an_add_on_installs_its_package_with_the_variants_picked(
    catalog: AddOnCatalog, text: str, requirement: str
) -> None:
    (choice,) = catalog.parse(text, "webapp")

    assert choice.requirement == requirement


def test_an_add_on_chosen_twice_is_refused(catalog: AddOnCatalog) -> None:
    with pytest.raises(UnknownAddOnError, match="chosen twice"):
        _ = catalog.parse("orm,orm:postgres", "cli")


def test_an_unknown_variant_names_the_ones_offered(catalog: AddOnCatalog) -> None:
    with pytest.raises(UnknownAddOnError, match=r"oracle is not one of its database drivers"):
        _ = catalog.parse("orm:oracle", "cli")


def test_a_variant_of_an_add_on_without_any_is_refused(catalog: AddOnCatalog) -> None:
    with pytest.raises(UnknownAddOnError, match=r"\(none\)"):
        _ = catalog.parse("scheduler:fast", "cli")
