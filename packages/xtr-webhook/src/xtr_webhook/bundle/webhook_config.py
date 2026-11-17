"""The one configuration an application writes to receive and send webhooks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

from xtr_webhook.client.webhook_id_store_interface import WebhookIdStoreInterface
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
    with the legacy scheme under the default header names, and sends through
    the application's default HTTP client.

    Attributes:
        http_client: The qualifier of the
            :class:`~xtr_http_client_contracts.HttpClientInterface` webhooks are
            sent through — a scoped client of the HTTP client configuration.
            ``None`` means the default, unqualified one.
        no_private_network: Whether that client is wrapped in a guard refusing
            to deliver into a private network, and what counts as one.
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
        id_store: The application's class remembering the ids of the webhooks
            already taken, built by the container. A webhook id it remembers
            is acknowledged with 202 and not handed on again. ``None`` hands on
            every webhook.
        id_ttl: How many seconds an id is remembered — as long as a sender
            may retry a webhook.
    """

    http_client: str | None = None
    no_private_network: NoPrivateNetworkConfig = field(default_factory=NoPrivateNetworkConfig)
    event_header_name: str = "Webhook-Event"
    id_header_name: str = "Webhook-Id"
    timestamp_header_name: str = "Webhook-Timestamp"
    signature_header_name: str = "Webhook-Signature"
    signing_algorithm: str = "sha256"
    signature_format: SignatureFormat | str = SignatureFormat.STANDARD
    timestamp_tolerance: int = 300
    routing: Mapping[str, RouteConfig] = field(default_factory=_no_routes)
    id_store: type[WebhookIdStoreInterface] | None = None
    id_ttl: int = 86_400

    def __post_init__(self) -> None:
        """Refuse values no service built from them could honour.

        Raises:
            InvalidArgumentError: When the tolerance is negative, the
                algorithm is not available, the format names no scheme, or
                ``id_ttl`` is below one.
        """
        if self.timestamp_tolerance < 0:
            raise InvalidArgumentError("timestamp_tolerance must be greater than or equal to 0.")
        if self.id_ttl < 1:
            raise InvalidArgumentError("id_ttl must be at least one second.")
        if self.signing_algorithm not in hashlib.algorithms_available:
            raise InvalidArgumentError(
                f'The signing algorithm "{self.signing_algorithm}" is not available.',
            )
        _ = SignatureFormat.parse(self.signature_format)
