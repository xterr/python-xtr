"""The import package is importable and ships the marker that publishes its types."""

from __future__ import annotations

from importlib.resources import files

import xtr_http_client_contracts


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_http_client_contracts").joinpath("py.typed").is_file()


def test_every_exported_name_resolves() -> None:
    missing = [
        name
        for name in xtr_http_client_contracts.__all__
        if not hasattr(xtr_http_client_contracts, name)
    ]

    assert missing == []


def test_the_whole_contract_is_reachable_from_the_package_itself() -> None:
    assert set(xtr_http_client_contracts.__all__) == {
        "OPTIONS_DEFAULTS",
        "ChunkInterface",
        "ClientError",
        "DecodingError",
        "HttpClientError",
        "HttpClientInterface",
        "HttpError",
        "QueryValue",
        "RedirectionError",
        "RequestOptions",
        "ResponseInterface",
        "ResponseStreamInterface",
        "ServerError",
        "TransportError",
        "TransportTimeoutError",
    }
