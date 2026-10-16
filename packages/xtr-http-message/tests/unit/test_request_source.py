"""Tests for :class:`xtr_http_message.request_source.RequestSource`."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_message import RequestSource

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _Source:
    """The smallest thing a request can be born connected over."""

    async def materialise(self) -> bytes:
        return b""

    def parsed_body(self) -> object | None:
        return None

    def uploaded_files(self) -> Mapping[str, object]:
        return {}

    def attributes(self) -> Mapping[str, object]:
        return {}


def test_a_source_answering_the_members_is_a_request_source() -> None:
    assert isinstance(_Source(), RequestSource)
