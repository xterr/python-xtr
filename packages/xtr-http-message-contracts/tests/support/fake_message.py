"""A message that satisfies the contract and carries no header and an empty body."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tests.support.fake_stream import FakeStream

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import StreamInterface

__all__ = ["FakeMessage"]


class FakeMessage:
    """Answers every question on the message contract, carrying nothing.

    Each ``with_*`` answers with the same instance, which an immutable message
    with nothing in it may: there is no state to keep apart.
    """

    def get_protocol_version(self) -> str:
        return "1.1"

    def with_protocol_version(self, version: str) -> Self:
        del version
        return self

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        return {}

    def has_header(self, name: str) -> bool:
        del name
        return False

    def get_header(self, name: str) -> Sequence[str]:
        del name
        return []

    def get_header_line(self, name: str) -> str:
        del name
        return ""

    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        del name, value
        return self

    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        del name, value
        return self

    def without_header(self, name: str) -> Self:
        del name
        return self

    def get_body(self) -> StreamInterface:
        return FakeStream()

    def with_body(self, body: StreamInterface) -> Self:
        del body
        return self
