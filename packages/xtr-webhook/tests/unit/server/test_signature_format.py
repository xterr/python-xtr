from __future__ import annotations

import pytest

from xtr_webhook.exception import InvalidArgumentError
from xtr_webhook.server import SignatureFormat

_REFUSED = '"nope" is not a signature format; use "legacy", "standard" or "transitional".'


def test_there_are_exactly_three_formats() -> None:
    assert {member.value for member in SignatureFormat} == {
        "legacy",
        "standard",
        "transitional",
    }


def test_a_member_is_its_own_string() -> None:
    assert SignatureFormat.LEGACY == "legacy"
    assert SignatureFormat.STANDARD == "standard"
    assert SignatureFormat.TRANSITIONAL == "transitional"


def test_a_member_reads_as_its_string_when_formatted() -> None:
    assert f"{SignatureFormat.TRANSITIONAL}" == "transitional"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("legacy", SignatureFormat.LEGACY),
        ("standard", SignatureFormat.STANDARD),
        ("transitional", SignatureFormat.TRANSITIONAL),
    ],
)
def test_parse_reads_the_string_form(value: str, expected: SignatureFormat) -> None:
    assert SignatureFormat.parse(value) is expected


@pytest.mark.parametrize("member", list(SignatureFormat))
def test_parse_returns_a_member_unchanged(member: SignatureFormat) -> None:
    assert SignatureFormat.parse(member) is member


def test_parse_names_the_word_it_refused_and_the_three_it_takes() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = SignatureFormat.parse("nope")

    assert str(refused.value) == _REFUSED


def test_a_refused_format_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="nope"):
        _ = SignatureFormat.parse("nope")


def test_parse_is_case_sensitive() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SignatureFormat.parse("LEGACY")
