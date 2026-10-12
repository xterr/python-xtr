"""The one configuration an application writes to receive and send webhooks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

from xtr_webhook.exception import InvalidArgumentError
from xtr_webhook.server.signature_format import SignatureFormat

from .no_private_network_config import NoPrivateNetworkConfig
from .route_config import RouteConfig

__all__ = ["WebhookConfig"]


def _no_routes() -> dict[str, RouteConfig]:
    """The empty routing a zero-config application starts with."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class WebhookConfig:
    """Values the bundle builds the endpoint's and the sender's services from.

    Buildable with no arguments: the zero-config path routes nothing, signs
    with the legacy scheme under the default header names, and sends through a
    client the bundle builds itself.

    Attributes:
        http_client: The qualifier of an ``httpx.AsyncClient`` the application
            registered, for the sender to post through. ``None`` means the
            bundle builds and owns its own.
        no_private_network: Whether the bundle-built client refuses to deliver
            into a private network, and what counts as one.
        event_header_name: The header the event's name travels in, where the
            signature scheme sends one.
        id_header_name: The header the event's id travels in.
        timestamp_header_name: The header the send time travels in.
        signature_header_name: The header the signature entries travel in.
        signing_algorithm: The digest the legacy signature is made with.
        signature_format: The signature scheme both ends must share — a
            :class:`~xtr_webhook.server.SignatureFormat` or the string one
            carries. Validated here; readers convert with
            :meth:`SignatureFormat.parse <xtr_webhook.server.SignatureFormat.parse>`.
        timestamp_tolerance: How many seconds either side of now an incoming
            signed timestamp may be. Zero turns the replay bound off.
        routing: What the endpoint does with each webhook type, by the type in
            the URL. Keys are kept verbatim — dashes too.
    """

    http_client: str | None = None
    no_private_network: NoPrivateNetworkConfig = field(default_factory=NoPrivateNetworkConfig)
    event_header_name: str = "Webhook-Event"
    id_header_name: str = "Webhook-Id"
    timestamp_header_name: str = "Webhook-Timestamp"
    signature_header_name: str = "Webhook-Signature"
    signing_algorithm: str = "sha256"
    signature_format: SignatureFormat | str = SignatureFormat.LEGACY
    timestamp_tolerance: int = 300
    routing: Mapping[str, RouteConfig] = field(default_factory=_no_routes)

    def __post_init__(self) -> None:
        """Refuse values no service built from them could honour.

        The guard cannot be combined with a client the application registered:
        wrapping one would need the client library's private internals and
        would still leave its mounts unguarded, so the combination is refused
        rather than half-honoured — leave ``http_client`` unset, or build the
        client with :class:`~xtr_webhook.bridge.httpx.NoPrivateNetworkTransport`.

        Raises:
            InvalidArgumentError: When the tolerance is negative, the
                algorithm is not available, the format names no scheme, or
                ``http_client`` is combined with the guard.
        """
        if self.timestamp_tolerance < 0:
            raise InvalidArgumentError("timestamp_tolerance must be greater than or equal to 0.")
        if self.signing_algorithm not in hashlib.algorithms_available:
            raise InvalidArgumentError(
                f'The signing algorithm "{self.signing_algorithm}" is not available.',
            )
        _ = SignatureFormat.parse(self.signature_format)
        if self.http_client is not None and self.no_private_network.enabled:
            raise InvalidArgumentError(
                "no_private_network cannot guard an httpx client you registered; leave "
                "http_client unset, or build your client with NoPrivateNetworkTransport.",
            )
