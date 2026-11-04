from __future__ import annotations

import pytest

from tests.support.wire import assert_folded, decode_parameters
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import ParameterizedHeader

LANGUAGE = "en-us"
# Upstream's iso-8859-1 byte 0x8F; as a character it is a C1 control the engine refuses.
NON_ASCII = "\xf8"


def test_the_value_is_returned_verbatim() -> None:
    assert ParameterizedHeader("Content-Type", "text/plain").get_value() == "text/plain"


def test_parameters_are_appended() -> None:
    header = ParameterizedHeader("Content-Type", "text/plain")

    header.set_parameters({"charset": "utf-8"})

    # Adapted (D1): the engine quotes every parameter value; RFC 2045 reads a quoted token
    # as the token.
    assert header.get_body_as_string() == 'text/plain; charset="utf-8"'


def test_a_space_in_a_parameter_results_in_a_quoted_string() -> None:
    # Adapted: Content-Disposition, since the engine writes only a media type in Content-Type.
    header = ParameterizedHeader("Content-Disposition", "attachment")

    header.set_parameters({"filename": "my file.txt"})

    assert header.get_body_as_string() == 'attachment; filename="my file.txt"'


def test_quotes_and_backslashes_are_escaped_in_a_quoted_string() -> None:
    header = ParameterizedHeader("Content-Disposition", "attachment")

    header.set_parameters({"filename": 'my "file" \\ 1.txt'})

    assert header.get_body_as_string() == 'attachment; filename="my \\"file\\" \\\\ 1.txt"'


def test_form_data_results_in_a_quoted_string() -> None:
    header = ParameterizedHeader("Content-Disposition", "form-data")

    header.set_parameters({"filename": "file.txt"})

    assert header.get_body_as_string() == 'form-data; filename="file.txt"'


# A form-data name or filename — escaped as browsers do, raw UTF-8 — is a FormDataPart case
# (tests/unit/part/multipart/test_form_data_part.py): the form writes its fields itself, the
# engine writes a non-ASCII parameter only in RFC 2231 form.


def test_long_parameters_are_broken_into_multiple_attribute_strings() -> None:
    value = "a" * 180
    header = ParameterizedHeader("Content-Disposition", "attachment")

    header.set_parameters({"filename": value})

    # Adapted (D1): RFC 2231 continuations, the folding rules, and the value read back.
    rendered = header.to_string()
    assert "filename*0" in rendered
    assert_folded(rendered)
    assert decode_parameters(rendered) == {"filename": value}


def test_encoded_parameter_data_reads_back_whatever_the_charset_and_language() -> None:
    value = "a" * 20 + NON_ASCII + "a" * 10
    header = ParameterizedHeader("Content-Disposition", "attachment")
    header.set_charset("iso-8859-1")
    header.set_value("attachment")
    header.set_parameters({"filename": value})
    header.set_language(LANGUAGE)

    rendered = header.to_string()

    # Adapted (D1): the engine writes RFC 2231 in UTF-8 without a language; decode and compare.
    assert rendered.isascii()
    assert decode_parameters(rendered) == {"filename": value}


def test_multiple_encoded_parameter_lines_read_back() -> None:
    value = "a" * 20 + NON_ASCII + "a" * 60
    header = ParameterizedHeader("Content-Disposition", "attachment")
    header.set_value("attachment")
    header.set_charset("utf-6")
    header.set_parameters({"filename": value})
    header.set_language(LANGUAGE)

    rendered = header.to_string()

    # Adapted (D1): the folding rules and the value read back instead of the continuations.
    assert_folded(rendered)
    assert decode_parameters(rendered) == {"filename": value}


def test_to_string() -> None:
    header = ParameterizedHeader("Content-Type", "text/html")

    header.set_parameters({"charset": "utf-8"})

    # Adapted (D1): the engine quotes the parameter value.
    assert header.to_string() == 'Content-Type: text/html; charset="utf-8"'


@pytest.mark.xfail(
    strict=True,
    raises=RfcComplianceError,
    reason="the engine writes a parameterized value only as a token, never as encoded words",
)
def test_the_value_can_be_encoded_if_non_ascii() -> None:
    header = ParameterizedHeader("X-Foo", f"fo{NON_ASCII}bar", {"lookslike": "foobar"})

    assert header.to_string().startswith("X-Foo: =?")


@pytest.mark.xfail(
    strict=True,
    raises=RfcComplianceError,
    reason="the engine writes a parameterized value only as a token, never as encoded words",
)
def test_the_value_and_a_parameter_can_be_encoded_if_non_ascii() -> None:
    value = f"fo{NON_ASCII}bar"
    header = ParameterizedHeader("X-Foo", value, {"says": value})

    assert decode_parameters(header.to_string()) == {"says": value}


def test_parameters_are_encoded_if_non_ascii() -> None:
    value = f"fo{NON_ASCII}bar"
    header = ParameterizedHeader("X-Foo", "bar")
    header.set_charset("iso-8859-1")

    header.set_parameters({"says": value})

    # Adapted (D1): decode and compare instead of the RFC 2231 bytes.
    rendered = header.to_string()
    assert rendered.startswith("X-Foo: bar; says*=")
    assert decode_parameters(rendered) == {"says": value}


@pytest.mark.parametrize("name", ["X-Foo", "Content-Type"])
def test_a_parameter_holding_a_control_character_is_refused(name: str) -> None:
    value = "text/plain" if name == "Content-Type" else "bar"
    header = ParameterizedHeader(name, value, {"says": "fo\x00bar"})

    # Adapted: upstream encodes the control character; the engine refuses it.
    with pytest.raises(RfcComplianceError):
        _ = header.to_string()


def test_a_content_type_parameter_is_encoded_the_engine_s_way() -> None:
    value = f"fo{NON_ASCII}bar"
    # Adapted: "text/plain", as the engine writes only a media type in Content-Type.
    header = ParameterizedHeader("Content-Type", "text/plain", {"says": value})
    header.set_charset("iso-8859-1")

    rendered = header.to_string()

    # Adapted (D1): RFC 2231 where upstream writes an encoded word in quotes; decode and compare.
    assert rendered.isascii()
    assert decode_parameters(rendered) == {"says": value}


def test_the_language_is_kept_though_the_engine_does_not_write_it() -> None:
    value = f"fo{NON_ASCII}bar"
    # Adapted: an ASCII value, the only kind the engine writes before parameters.
    header = ParameterizedHeader("X-Foo", "bar")
    header.set_charset("iso-8859-1")
    header.set_language("en")

    header.set_parameters({"says": value})

    assert header.get_language() == "en"
    assert decode_parameters(header.to_string()) == {"says": value}


def test_set_body() -> None:
    header = ParameterizedHeader("Content-Type", "text/html")

    header.set_body("text/plain")

    assert header.get_value() == "text/plain"


def test_set_body_refuses_what_is_not_text() -> None:
    header = ParameterizedHeader("Content-Type", "text/html")

    with pytest.raises(InvalidArgumentError):
        header.set_body(42)


def test_get_body() -> None:
    assert ParameterizedHeader("Content-Type", "text/plain").get_body() == "text/plain"


def test_set_parameter() -> None:
    header = ParameterizedHeader("Content-Type", "text/html")
    header.set_parameters({"charset": "utf-8", "delsp": "yes"})

    header.set_parameter("delsp", "no")

    assert header.get_parameters() == {"charset": "utf-8", "delsp": "no"}


def test_get_parameter() -> None:
    header = ParameterizedHeader("Content-Type", "text/html")

    header.set_parameters({"charset": "utf-8", "delsp": "yes"})

    assert header.get_parameter("charset") == "utf-8"


def test_a_missing_or_unset_parameter_reads_as_empty() -> None:
    header = ParameterizedHeader("Content-Type", "text/html", {"format": None})

    assert header.get_parameter("charset") == ""
    assert header.get_parameter("format") == ""


def test_a_parameter_set_to_none_is_not_written() -> None:
    header = ParameterizedHeader("Content-Type", "text/html", {"charset": "utf-8", "format": None})

    assert header.get_body_as_string() == 'text/html; charset="utf-8"'


INVALID_PARAMETER_NAMES = {
    "CRLF injection": "name\r\nX-Injected: bar",
    "LF only": "name\nX-Injected: bar",
    "CR only": "name\rX-Injected: bar",
    "space": "my param",
    "semicolon": "na;me",
    "equals": "na=me",
    "quote": 'na"me',
}


def _invalid_names() -> list[object]:
    return [pytest.param(name, id=case) for case, name in INVALID_PARAMETER_NAMES.items()]


def _assert_name_refused(caught: pytest.ExceptionInfo[RfcComplianceError], name: str) -> None:
    assert str(caught.value) == (
        f'The parameter name "{repr(name)[1:-1]}" contains non-token characters.'
    )


@pytest.mark.parametrize("name", _invalid_names())
def test_the_constructor_rejects_an_invalid_parameter_name(name: str) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = ParameterizedHeader("Content-Type", "text/plain", {name: "value"})

    _assert_name_refused(caught, name)


@pytest.mark.parametrize("name", _invalid_names())
def test_set_parameter_rejects_an_invalid_parameter_name(name: str) -> None:
    header = ParameterizedHeader("Content-Type", "text/plain")

    with pytest.raises(RfcComplianceError) as caught:
        header.set_parameter(name, "value")

    _assert_name_refused(caught, name)


@pytest.mark.parametrize("name", _invalid_names())
def test_set_parameters_rejects_an_invalid_parameter_name(name: str) -> None:
    header = ParameterizedHeader("Content-Type", "text/plain")

    with pytest.raises(RfcComplianceError) as caught:
        header.set_parameters({name: "value"})

    _assert_name_refused(caught, name)


LONGEST_NAME = 40


@pytest.mark.parametrize("value", ["v", "v" * 5000, "\U0001f600" * 2000])
def test_a_parameter_name_of_the_longest_length_is_written_whatever_its_value(value: str) -> None:
    header = ParameterizedHeader("Content-Disposition", "attachment")
    header.set_parameter("x" * LONGEST_NAME, value)

    assert decode_parameters(header.to_string()) == {"x" * LONGEST_NAME: value}


def test_a_parameter_name_too_long_for_a_folded_line_is_refused() -> None:
    # Longer, an RFC 2231 section of the value may not fit on a line next to the name.
    header = ParameterizedHeader("Content-Type", "text/plain")

    with pytest.raises(RfcComplianceError) as caught:
        header.set_parameter("x" * (LONGEST_NAME + 1), "v")

    assert str(caught.value) == (
        f"A parameter name must be at most {LONGEST_NAME} characters long "
        f"({LONGEST_NAME + 1} given)."
    )
    assert header.get_parameters() == {}
