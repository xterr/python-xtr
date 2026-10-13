"""The address a request came from, placed in a network."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import IpsRequestMatcher

if TYPE_CHECKING:
    from collections.abc import Sequence


def _arrived_from(client: object) -> ServerRequest:
    return ServerRequest("GET", "/", server_params={"client": client})


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("ips", "expected"),
    [
        ([], True),
        ("127.0.0.1", True),
        ("192.168.0.1", False),
        ("127.0.0.1, ::1", True),
        ("192.168.0.1, ::1", False),
        (["127.0.0.1", "::1"], True),
        (["192.168.0.1", "::1"], False),
        (["1.1.1.1", "2.2.2.2", "127.0.0.1, ::1"], True),
        (["1.1.1.1", "2.2.2.2", "192.168.0.1, ::1"], False),
        (["192.168.1.0/24"], False),
        (["127.0.0.1/32"], True),
    ],
)
async def test_it_matches_the_client_address(ips: Sequence[str] | str, expected: bool) -> None:
    matcher = IpsRequestMatcher(ips)

    assert await matcher.matches(_arrived_from(("127.0.0.1", 36842))) is expected


@pytest.mark.anyio
async def test_it_refuses_a_request_whose_address_the_server_did_not_report() -> None:
    matcher = IpsRequestMatcher("127.0.0.1")

    assert await matcher.matches(ServerRequest("GET", "/")) is False


@pytest.mark.anyio
@pytest.mark.parametrize("client", [None, (), ("",), (36842,), "127.0.0.1"])
async def test_it_refuses_a_request_whose_address_is_not_one(client: object) -> None:
    matcher = IpsRequestMatcher("127.0.0.1")

    assert await matcher.matches(_arrived_from(client)) is False


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_names_no_address() -> None:
    matcher = IpsRequestMatcher([])

    assert await matcher.matches(ServerRequest("GET", "/")) is True
