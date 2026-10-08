from __future__ import annotations

from xtr_cli.exception import UnknownAddOnError


def test_it_names_the_add_on_and_the_reason() -> None:
    error = UnknownAddOnError("queue", "a cli project can take orm")

    assert str(error) == "cannot add 'queue': a cli project can take orm"
