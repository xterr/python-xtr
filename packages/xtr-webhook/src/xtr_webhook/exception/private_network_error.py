"""An outgoing webhook was stopped before it reached a private address."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from .delivery_error import DeliveryError

__all__ = ["PrivateNetworkError"]


@final
class PrivateNetworkError(DeliveryError):
    """A host an outgoing webhook named resolves into a network it may not reach.

    A subscriber url is usually data — chosen by whoever registered it — so a
    webhook is a way to ask this process to fetch an address only this process can
    see: another service on the same network, a database admin port, a cloud
    provider's metadata endpoint handing out credentials. The guard resolves the
    host first and refuses on what it resolves to, not on how it is written, so
    neither a name pointing inwards nor an address spelled unusually gets through.

    A :class:`DeliveryError <xtr_webhook.exception.DeliveryError>`, so a sender
    catches one refusal for "it did not arrive" — though this one will not arrive
    on a retry either, since nothing about the network changes by trying again.

    Attributes:
        host: The host the webhook named.
        address: The address it resolved to, which the guard refused.
        status_code: Always ``0``: nothing answered, because nothing was sent.
        url: The host, which is all the guard is told.
    """

    host: str
    address: str

    def __init__(self, host: str, address: str) -> None:
        """Record the host and the address that stopped the delivery.

        Args:
            host: The host the webhook named.
            address: The address it resolved to.
        """
        self.host = host
        self.address = address
        super().__init__(0, host)

    @override
    def _reason(self) -> str:
        return (
            f'The host "{self.host}" resolves to "{self.address}", which is in a private network.'
        )
