"""The remember-me cookie's value: the layout every handler writes and reads."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.remember_me import RememberMeDetails

pytestmark = pytest.mark.anyio

#: An identifier whose base64 encoding carries the characters the URL-safe
#: alphabet rewrites: ``w7/Dvg==`` becomes ``w7_Dvg~~``.
_REWRITTEN = "ÿþ"


def test_the_value_lays_out_as_the_empty_field_the_identifier_the_expiry_and_the_value() -> None:
    assert str(RememberMeDetails("ada", 123, "series:value")) == ":YWRh:123:series:value"


def test_the_identifier_is_written_in_the_url_safe_alphabet() -> None:
    encoded = base64.b64encode(_REWRITTEN.encode("utf-8")).decode("ascii")

    assert encoded == "w7/Dvg=="
    assert str(RememberMeDetails(_REWRITTEN, 1, "v")) == ":w7_Dvg~~:1:v"


def test_a_raw_cookie_reads_back_into_the_details_it_was_written_from() -> None:
    details = RememberMeDetails(_REWRITTEN, 123, "series:value")

    read = RememberMeDetails.from_raw_cookie(str(details))

    assert read.get_user_identifier() == _REWRITTEN
    assert read.get_expires() == 123
    assert read.get_value() == "series:value"


def test_a_raw_cookie_with_no_separator_is_decoded_as_a_whole_first() -> None:
    details = RememberMeDetails("ada", 123, "value")
    whole = base64.b64encode(str(details).encode("utf-8")).decode("ascii")

    read = RememberMeDetails.from_raw_cookie(whole)

    assert read.get_user_identifier() == "ada"
    assert read.get_expires() == 123
    assert read.get_value() == "value"


def test_a_value_with_too_few_fields_is_refused_as_invalid_data() -> None:
    with pytest.raises(AuthenticationError, match="invalid data"):
        _ = RememberMeDetails.from_raw_cookie(":YWRh:123")


def test_a_value_with_no_separator_at_all_is_refused_as_invalid_data() -> None:
    with pytest.raises(AuthenticationError, match="invalid data"):
        _ = RememberMeDetails.from_raw_cookie("nonsense")


def test_an_identifier_outside_the_base64_alphabet_is_refused_by_name() -> None:
    with pytest.raises(AuthenticationError, match="outside the base64 alphabet"):
        _ = RememberMeDetails.from_raw_cookie(":not~b64!:123:value")


def test_an_expiry_that_is_not_a_number_is_refused_as_invalid_data() -> None:
    with pytest.raises(AuthenticationError, match="invalid data"):
        _ = RememberMeDetails.from_raw_cookie(":YWRh:soon:value")


def test_a_persistent_token_writes_its_series_and_value_as_the_cookies_own() -> None:
    token = PersistentToken("ada", "the-series", "the-value", datetime.now(UTC))

    details = RememberMeDetails.from_persistent_token(token, 123)

    assert details.get_user_identifier() == "ada"
    assert details.get_expires() == 123
    assert details.get_value() == "the-series:the-value"


def test_with_value_moves_only_the_value() -> None:
    details = RememberMeDetails("ada", 123, "old")

    moved = details.with_value("new")

    assert moved.get_user_identifier() == "ada"
    assert moved.get_expires() == 123
    assert moved.get_value() == "new"
    assert details.get_value() == "old"
