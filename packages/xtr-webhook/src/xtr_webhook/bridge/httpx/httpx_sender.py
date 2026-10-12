"""The sender that posts a built webhook through an httpx client."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.server import HttpSenderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

__all__ = ["HttpxSender"]


@final
class HttpxSender(HttpSenderInterface):
    """Posts the exact bytes it is handed and answers with the status code.

    Redirects are never followed, whatever the client was built with: a 3xx
    comes back as the answer and the transport treats it as a refusal. Following
    one would re-send a signed body to whatever address the receiver pointed
    at — an address nobody registered — and would hollow out the private-network
    guard, which checks the request's own host, not where a redirect leads.

    The client is taken, not built: whoever owns it decides its timeouts, its
    limits and when it closes, and can wrap its transport in
    :class:`NoPrivateNetworkTransport
    <xtr_webhook.bridge.httpx.NoPrivateNetworkTransport>`.
    """

    __slots__ = ("_client",)

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Take the client every post goes through.

        Args:
            client: The client to post with.
        """
        self._client = client

    @override
    async def post(self, url: str, headers: Mapping[str, str], body: bytes) -> int:
        """Post ``body`` to ``url`` under ``headers``.

        Args:
            url: Where to post.
            headers: The headers to send, exactly as built.
            body: The exact bytes to send.

        Returns:
            The status code the receiver answered with.
        """
        response = await self._client.post(
            url,
            headers=headers,
            content=body,
            follow_redirects=False,
        )

        return response.status_code
