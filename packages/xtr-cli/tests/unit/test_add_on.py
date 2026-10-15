from __future__ import annotations

from xtr_cli import AddOn

_ORM = AddOn("orm", "Databases.", "xtr-orm", ("pool",), ("sqlite", "postgres"), ("sqlite",))


def test_the_requirement_carries_the_extras_and_the_variants() -> None:
    assert _ORM.requirement(("postgres",)) == "xtr-orm[pool,postgres]"


def test_an_add_on_without_extras_is_its_distribution() -> None:
    assert AddOn("x", "X.", "xtr-x").requirement(()) == "xtr-x"


def test_an_add_on_with_no_templates_fits_every_one() -> None:
    assert _ORM.fits("cli")
    assert _ORM.fits("webapp")


def test_an_add_on_limited_to_templates_fits_only_those() -> None:
    web_only = AddOn("security", "S.", "xtr-security", templates=("webapp",))

    assert web_only.fits("webapp")
    assert not web_only.fits("cli")
