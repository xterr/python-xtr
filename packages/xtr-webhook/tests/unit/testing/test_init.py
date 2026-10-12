from __future__ import annotations

from xtr_webhook import testing

_EXPORTED = [
    "ParserCase",
    "assert_parses",
    "parser_cases",
]


def test_every_exported_name_resolves() -> None:
    assert [name for name in testing.__all__ if not hasattr(testing, name)] == []


def test_it_exports_the_case_and_the_two_functions_around_it() -> None:
    assert sorted(testing.__all__) == _EXPORTED
