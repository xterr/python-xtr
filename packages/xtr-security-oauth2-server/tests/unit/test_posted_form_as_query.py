"""Reading an authorization request a browser posted as a form."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl

import pytest
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from tests.support.messages import MultiValuedForm, server_request
from xtr_security_oauth2_server.posted_form_as_query import posted_form_as_query

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_FORM: Final = "application/x-www-form-urlencoded"

_ASKING: Final = (
    ("response_type", "code"),
    ("client_id", "client-1"),
    ("redirect_uri", "https://client.test/callback"),
    ("state", "the-opaque-state"),
)


def _posted(
    form: Mapping[str, str] | None = None,
    *,
    content_type: str | None = _FORM,
    query: Mapping[str, object] | None = None,
) -> ServerRequestInterface:
    """Return a ``POST`` to the authorization endpoint carrying ``form``."""
    return server_request(
        "POST",
        "/authorize",
        headers={} if content_type is None else {"Content-Type": content_type},
        parsed_body=form,
        query_params=query,
    )


async def test_a_get_is_handed_back_as_it_arrived() -> None:
    request = server_request("GET", "/authorize", query_params=dict(_ASKING))

    assert await posted_form_as_query(request) is request


async def test_a_post_whose_query_asks_is_read_from_its_query() -> None:
    # The consent page posting the original query back, its decision in the body.
    request = _posted(MultiValuedForm([("allow", "yes")]), query=dict(_ASKING))

    assert await posted_form_as_query(request) is request


async def test_a_posted_form_becomes_the_query_the_grants_read() -> None:
    read = await posted_form_as_query(_posted(MultiValuedForm(_ASKING)))

    assert dict(read.get_query_params()) == dict(_ASKING)


async def test_a_posted_form_is_written_into_the_uri_as_well() -> None:
    # Whatever reads the query string rather than the parameters — a step
    # saving the request to come back to — reads the same request.
    read = await posted_form_as_query(_posted(MultiValuedForm(_ASKING)))

    assert parse_qsl(read.get_uri().get_query()) == list(_ASKING)
    assert read.get_uri().get_path() == "/authorize"


async def test_a_parameter_the_form_repeats_stays_visible_as_repeated() -> None:
    # The server refuses a repeated response_type only if it can still see it.
    form = MultiValuedForm([*_ASKING, ("response_type", "token")])

    read = await posted_form_as_query(_posted(form))

    query = read.get_query_params()
    assert isinstance(query, MultiValuedForm)
    assert query.getlist("response_type") == ("code", "token")
    uri_query = parse_qsl(read.get_uri().get_query())
    assert [value for name, value in uri_query if name == "response_type"] == ["code", "token"]


async def test_a_form_parsed_into_a_plain_mapping_is_read_too() -> None:
    read = await posted_form_as_query(_posted(dict(_ASKING)))

    assert parse_qsl(read.get_uri().get_query()) == list(_ASKING)


async def test_a_form_with_no_field_reads_as_a_request_naming_nothing() -> None:
    # Left to the server to refuse, naming the response_type it needs.
    read = await posted_form_as_query(_posted())

    assert dict(read.get_query_params()) == {}


async def test_a_form_content_type_is_read_without_its_parameters_or_case() -> None:
    content_type = "Application/X-WWW-Form-Urlencoded; charset=utf-8"

    read = await posted_form_as_query(_posted(MultiValuedForm(_ASKING), content_type=content_type))

    assert read.get_query_params()["client_id"] == "client-1"


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "multipart/form-data; boundary=x", None],
)
async def test_a_post_that_is_no_form_is_refused(content_type: str | None) -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = await posted_form_as_query(_posted(content_type=content_type))

    assert raised.value.get_error_type() == "invalid_request"
    assert "application/x-www-form-urlencoded" in str(raised.value.get_hint())


async def test_a_posted_form_beside_a_query_is_refused() -> None:
    # Two places to read one request from: neither is guessed at.
    request = _posted(MultiValuedForm(_ASKING), query={"client_id": "client-2"})

    with pytest.raises(OAuthServerError) as raised:
        _ = await posted_form_as_query(request)

    assert raised.value.get_error_type() == "invalid_request"


async def test_a_request_asked_for_in_both_the_query_and_the_form_is_refused() -> None:
    request = _posted(MultiValuedForm(_ASKING), query=dict(_ASKING))

    with pytest.raises(OAuthServerError) as raised:
        _ = await posted_form_as_query(request)

    assert raised.value.get_error_type() == "invalid_request"
