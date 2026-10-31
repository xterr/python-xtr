from __future__ import annotations

import pytest

from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import IdentificationHeader


def test_the_value_matches_the_msg_id_grammar() -> None:
    header = IdentificationHeader("Message-ID", "id-left@id-right")

    assert header.get_body_as_string() == "<id-left@id-right>"


def test_the_id_can_be_retrieved_verbatim() -> None:
    assert IdentificationHeader("Message-ID", "id-left@id-right").get_id() == "id-left@id-right"


def test_multiple_ids_can_be_set() -> None:
    header = IdentificationHeader("References", "c@d")

    header.set_ids(["a@b", "x@y"])

    assert header.get_ids() == ["a@b", "x@y"]


def test_setting_multiple_ids_produces_a_list_value() -> None:
    header = IdentificationHeader("References", ["a@b", "x@y"])

    assert header.get_body_as_string() == "<a@b> <x@y>"


def test_the_id_left_can_be_quoted() -> None:
    header = IdentificationHeader("References", '"ab"@c')

    assert header.get_id() == '"ab"@c'
    assert header.get_body_as_string() == '<"ab"@c>'


@pytest.mark.xfail(
    strict=True,
    raises=RfcComplianceError,
    reason=(
        "a quoted pair in an id reads back without its backslash — another id — and a reader "
        "taking '>' for the end of an id cuts it short: neither is written"
    ),
)
def test_the_id_left_can_contain_angles_as_quoted_pairs() -> None:
    header = IdentificationHeader("References", '"a\\<\\>b"@c')

    assert header.get_id() == '"a\\<\\>b"@c'
    assert header.get_body_as_string() == '<"a\\<\\>b"@c>'


def test_the_id_left_can_be_a_dot_atom() -> None:
    header = IdentificationHeader("References", "a.b+&%$.c@d")

    assert header.get_id() == "a.b+&%$.c@d"
    assert header.get_body_as_string() == "<a.b+&%$.c@d>"


@pytest.mark.parametrize("ids", ["a b c@d", "a@b c d", "abc"])
def test_an_id_outside_the_msg_id_grammar_is_refused(ids: str) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = IdentificationHeader("References", ids)

    assert str(caught.value) == (
        "An identifier of the References header is not a message identifier: "
        "id-left@id-right (RFC 5322, 3.6.4)."
    )


@pytest.mark.parametrize(
    "identifier", ["a\r\nBcc: v@e.x", "a\udc80@b", "a@b\u2028c", "a@b\udc80.test", "a@\x85.de"]
)
def test_a_refused_id_never_reaches_the_error_raw(identifier: str) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = IdentificationHeader("References", identifier)

    errors = [caught.value, caught.value.__cause__]
    assert identifier not in str(caught.value)
    for error in errors:
        assert not any(c in str(error) for c in ("\r", "\n", "\x85", "\u2028", "\udc80"))


def test_the_id_right_can_be_a_dot_atom() -> None:
    header = IdentificationHeader("References", "a@b.c+&%$.d")

    assert header.get_id() == "a@b.c+&%$.d"
    assert header.get_body_as_string() == "<a@b.c+&%$.d>"


def test_the_id_right_can_be_a_literal() -> None:
    header = IdentificationHeader("References", "a@[1.2.3.4]")

    assert header.get_id() == "a@[1.2.3.4]"
    assert header.get_body_as_string() == "<a@[1.2.3.4]>"


def test_the_id_right_is_idn_encoded() -> None:
    header = IdentificationHeader("References", "a@ä")

    assert header.get_id() == "a@ä"
    assert header.get_body_as_string() == "<a@xn--4ca>"


def test_an_id_right_idna_refuses_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="message identifier"):
        _ = IdentificationHeader("References", "a@-ä")


def test_set_body() -> None:
    header = IdentificationHeader("Message-ID", "c@d")

    header.set_body("a@b")

    assert header.get_ids() == ["a@b"]


def test_set_body_takes_a_list_and_refuses_anything_else() -> None:
    header = IdentificationHeader("References", "c@d")

    header.set_body(["a@b", "x@y"])
    assert header.get_ids() == ["a@b", "x@y"]

    with pytest.raises(InvalidArgumentError):
        header.set_body(42)
    with pytest.raises(InvalidArgumentError):
        header.set_body([42])


def test_get_body() -> None:
    assert IdentificationHeader("Message-ID", "a@b").get_body() == ["a@b"]


def test_there_is_no_id_once_the_list_is_emptied() -> None:
    header = IdentificationHeader("References", "a@b")

    header.set_ids([])

    assert header.get_id() is None


def test_the_string_value() -> None:
    header = IdentificationHeader("References", ["a@b", "x@y"])

    assert header.to_string() == "References: <a@b> <x@y>"
