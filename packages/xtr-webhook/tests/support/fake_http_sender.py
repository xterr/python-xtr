"""A sender that answers a scripted status and records every post."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.server import HttpSenderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class FakeHttpSender(HttpSenderInterface):
    """Answers ``status_code`` every time; ``posts`` keeps every call, in order.

    Recording the headers mapping itself rather than a copy is what lets a test
    see which dict the transport handed over — the request's own, or a copy.
    """

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.posts: list[tuple[str, Mapping[str, str], bytes]] = []

    @override
    async def post(self, url: str, headers: Mapping[str, str], body: bytes) -> int:
        self.posts.append((url, headers, body))

        return self.status_code
