"""Whether a class asked for its schema is asked where a type declares it."""

from __future__ import annotations

from xtr_serializer.mapping._declaration_sites import declaring, is_declaring


def test_no_schema_is_built_for_a_declaration_unless_said() -> None:
    assert not is_declaring()


def test_a_schema_is_built_for_a_declaration_until_said_no_more() -> None:
    with declaring():
        inside = is_declaring()

    assert (inside, is_declaring()) == (True, False)
