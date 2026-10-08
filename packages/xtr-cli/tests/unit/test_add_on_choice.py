from __future__ import annotations

from xtr_cli import AddOn, AddOnChoice

_ORM = AddOn("orm", "Databases.", "xtr-orm", ("di",), ("sqlite", "postgres"), ("sqlite",))


def test_the_choice_spells_its_variants_the_way_with_reads_them() -> None:
    assert AddOnChoice(_ORM, ("sqlite", "postgres")).spelling == "orm:sqlite+postgres"


def test_a_choice_of_no_variant_keeps_the_colon_so_the_defaults_are_not_taken() -> None:
    assert AddOnChoice(_ORM, ()).spelling == "orm:"


def test_the_default_variants_are_spelled_by_the_name_alone() -> None:
    assert AddOnChoice(_ORM, ("sqlite",)).spelling == "orm"


def test_an_add_on_without_variants_is_spelled_by_its_name() -> None:
    assert AddOnChoice(AddOn("lock", "L.", "xtr-lock"), ()).spelling == "lock"


def test_the_requirement_is_the_add_ons_with_the_variants_picked() -> None:
    assert AddOnChoice(_ORM, ("postgres",)).requirement == "xtr-orm[di,postgres]"
