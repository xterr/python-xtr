from __future__ import annotations

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport import Dsn
from xtr_mailer.transport.smtp._esmtp_dsn_options import (
    read_count,
    read_flag,
    read_number,
    read_text,
    refusal,
)


@pytest.mark.parametrize("value", ["abc", "-1.5e3", "", "a" * 40])
def test_a_refusal_shows_a_plain_word(value: str) -> None:
    assert str(refusal("key", "a thing", value)) == (
        f'The "key" option is not valid: it must be a thing, "{value}" given.'
    )


@pytest.mark.parametrize("value", [None, "a b", "x@y", "a" * 41, "[::1]", "é"])
def test_a_refusal_leaves_out_anything_else(value: str | None) -> None:
    assert str(refusal("key", "a thing", value)) == (
        'The "key" option is not valid: it must be a thing.'
    )


def test_an_unset_option_reads_as_none() -> None:
    dsn = Dsn("smtp", "localhost")

    assert read_text(dsn, "key", "a thing") is None
    assert read_number(dsn, "key", "a number") is None
    assert read_count(dsn, "key", "a count") is None


@pytest.mark.parametrize(
    ("value", "number"),
    [("1", 1.0), (" 2.5 ", 2.5), (".5", 0.5), ("1.", 1.0), ("1e2", 100.0), ("0", 0.0)],
)
def test_a_number_is_read(value: str, number: float) -> None:
    assert read_number(Dsn("smtp", "h", options={"key": value}), "key", "a number") == number


def test_a_positive_number_refuses_zero() -> None:
    with pytest.raises(InvalidArgumentError, match="a number"):
        _ = read_number(Dsn("smtp", "h", options={"key": "0"}), "key", "a number", positive=True)


@pytest.mark.parametrize("value", ["1_000", "0x10", "nan", "infinity", "+"])
def test_what_is_not_written_as_a_decimal_number_is_refused(value: str) -> None:
    with pytest.raises(InvalidArgumentError, match="a number"):
        _ = read_number(Dsn("smtp", "h", options={"key": value}), "key", "a number")


def test_a_count_is_read() -> None:
    assert read_count(Dsn("smtp", "h", options={"key": " 12 "}), "key", "a count") == 12


@pytest.mark.parametrize(("value", "flag"), [(None, True), ("", True), ("0", False), ("on", True)])
def test_a_flag_is_on_unless_turned_off(value: str | None, flag: bool) -> None:
    assert read_flag(Dsn("smtp", "h", options={"key": value}), "key") is flag
