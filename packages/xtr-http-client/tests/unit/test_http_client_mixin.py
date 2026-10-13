from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_client_contracts import OPTIONS_DEFAULTS

from xtr_http_client import HttpClientMixin
from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_client_starts_from_the_contract_defaults() -> None:
    client = HttpClientMixin()

    assert client._default_options["timeout"] == OPTIONS_DEFAULTS.get("timeout")
    assert client._default_options["max_redirects"] == 20


def test_the_defaults_a_client_was_built_with_win_over_the_contract_ones() -> None:
    client = HttpClientMixin({"timeout": 2.0, "headers": {"X-Trace": "abc"}})

    assert client._default_options["timeout"] == 2.0
    assert client._default_options["headers"] == {"X-Trace": "abc"}


def test_a_client_with_other_options_is_a_copy_of_the_one_it_came_from() -> None:
    client = HttpClientMixin({"timeout": 2.0})

    other = client.with_options(timeout=3.0, headers={"X-Trace": "abc"})

    assert other is not client
    assert other._default_options["timeout"] == 3.0
    assert client._default_options["timeout"] == 2.0
    assert other._default_options["headers"] == {"X-Trace": "abc"}
    assert client._default_options["headers"] == {}


def test_a_client_with_an_option_no_client_knows_is_refused() -> None:
    client = HttpClientMixin()
    # An untyped caller is exactly what the refusal is here for; the typed one
    # is refused by `RequestOptions` before anything runs.
    untyped = cast("Callable[..., object]", client.with_options)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = untyped(timout=1.0)

    assert 'Unsupported option "timout" passed to "HttpClientMixin"' in str(raised.value)


def test_the_options_a_request_merges_over_are_the_ones_the_client_keeps() -> None:
    client = HttpClientMixin()

    merged = client.merge_default_options({"timeout": 5.0}, client._default_options)

    assert merged["timeout"] == 5.0
    assert merged["max_redirects"] == 20


def test_an_option_the_client_knows_is_let_through() -> None:
    client = HttpClientMixin()

    client.validate_options({"timeout": 5.0})


def test_an_option_the_client_does_not_know_is_refused_on_its_own() -> None:
    client = HttpClientMixin()

    with pytest.raises(InvalidArgumentError) as raised:
        client.validate_options({"timout": 5.0})

    assert str(raised.value).startswith('Unsupported option "timout" passed to "HttpClientMixin"')


def test_a_method_of_uppercase_letters_is_accepted() -> None:
    HttpClientMixin.validate_method("GET")


def test_a_method_of_nothing_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="cannot be empty"):
        HttpClientMixin.validate_method("")


@pytest.mark.parametrize("method", ["get", "Get", "GET2", "GÉT"])
def test_a_method_that_is_not_uppercase_letters_is_refused(method: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_method(method)

    assert str(raised.value) == (
        f'Invalid HTTP method "{method}", only uppercase letters are accepted.'
    )


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"auth_basic": "user:password"},
        {"auth_basic": ("user",)},
        {"auth_basic": ("user", "password")},
        {"auth_bearer": "a-token"},
    ],
)
def test_credentials_a_client_can_send_are_accepted(options: dict[str, object]) -> None:
    HttpClientMixin.validate_auth(options)


def test_more_than_two_basic_credential_parts_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_auth({"auth_basic": ("user", "password", "nonsense")})

    assert str(raised.value) == ('Option "auth_basic" must contain 1 or 2 elements, "3" given.')


def test_a_basic_credential_of_another_shape_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_auth({"auth_basic": 7})

    assert str(raised.value) == ('Option "auth_basic" must be a string or a tuple, "int" given.')


def test_a_bearer_token_that_is_not_text_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_auth({"auth_bearer": 7})

    assert str(raised.value) == 'Option "auth_bearer" must be a string, "int" given.'


def test_a_bearer_token_no_header_could_carry_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_auth({"auth_bearer": "ab\ncd"})

    assert str(raised.value) == ('Invalid character found in option "auth_bearer": "ab\\ncd".')


def test_two_sets_of_credentials_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_auth({"auth_basic": "user:password", "auth_bearer": "a-token"})

    assert str(raised.value) == (
        'Define either the "auth_basic" or the "auth_bearer" option, setting both is not supported.'
    )


@pytest.mark.parametrize(
    "options",
    [{}, {"json": None, "body": b"a=1"}, {"json": {"a": 1}}, {"json": {"a": 1}, "body": b""}],
)
def test_a_request_that_says_what_to_send_once_is_accepted(options: dict[str, object]) -> None:
    HttpClientMixin.validate_body(options)


def test_a_json_document_and_a_body_together_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        HttpClientMixin.validate_body({"json": {"a": 1}, "body": b"a=1"})

    assert str(raised.value) == (
        'Define either the "json" or the "body" option, setting both is not supported.'
    )
