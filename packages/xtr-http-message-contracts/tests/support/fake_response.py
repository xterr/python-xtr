"""A response that satisfies the contract and says only that it went well."""

from __future__ import annotations

from typing import Self

from tests.support.fake_message import FakeMessage

__all__ = ["FakeResponse"]


class FakeResponse(FakeMessage):
    """Answers the response contract on top of :class:`FakeMessage`."""

    def get_status_code(self) -> int:
        return 200

    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        del code, reason_phrase
        return self

    def get_reason_phrase(self) -> str:
        return "OK"
