from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_client_contracts import HttpClientInterface

from xtr_http_client import HttpClient, HttpxHttpClient
from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions

pytestmark = pytest.mark.anyio


async def test_a_client_comes_back_without_the_caller_naming_one() -> None:
    client = HttpClient.create()

    assert isinstance(client, HttpClientInterface)
    assert isinstance(client, HttpxHttpClient)

    await client.aclose()


async def test_the_options_it_is_given_become_the_client_s_defaults() -> None:
    client = HttpClient.create(max_host_connections=2, base_uri="http://example.test/")

    assert isinstance(client, HttpxHttpClient)
    assert client._default_options["base_uri"] == "http://example.test/"

    await client.aclose()


def test_an_option_the_client_does_not_know_is_refused_on_the_spot() -> None:
    unknown = cast("RequestOptions", cast("object", {"timeuot": 5}))

    with pytest.raises(InvalidArgumentError, match="Unsupported option"):
        _ = HttpClient.create(**unknown)
