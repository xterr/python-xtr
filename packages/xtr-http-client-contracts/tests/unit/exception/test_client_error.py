from __future__ import annotations

from xtr_http_client_contracts import ClientError, HttpError, RedirectionError, ServerError


def test_it_is_an_http_error() -> None:
    assert issubclass(ClientError, HttpError)


def test_catching_it_leaves_the_other_status_ranges_alone() -> None:
    assert not issubclass(ServerError, ClientError)
    assert not issubclass(RedirectionError, ClientError)
