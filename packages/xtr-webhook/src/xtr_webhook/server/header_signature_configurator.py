"""The signature that proves a webhook came from here, and was not replayed."""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook._standard_webhooks_signature import sign
from xtr_webhook.exception import InvalidArgumentError, LogicError

from .request_configurator_interface import RequestConfiguratorInterface
from .signature_format import SignatureFormat

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from .outgoing_request import OutgoingRequest

__all__ = ["HeaderSignatureConfigurator"]


@final
class HeaderSignatureConfigurator(RequestConfiguratorInterface):
    """Signs what the earlier configurators built, into one header.

    It runs last, because it signs their output: the body one wrote and the
    timestamp another wrote. Under the transitional format it emits both
    signatures, space separated, so a receiver mid-migration accepts whichever it
    already understands and neither sender nor receiver has to change on the same
    day.
    """

    __slots__ = (
        "_algorithm",
        "_signature_format",
        "_signature_header_name",
        "_timestamp_header_name",
    )

    def __init__(
        self,
        algorithm: str = "sha256",
        signature_header_name: str = "Webhook-Signature",
        signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
        timestamp_header_name: str = "Webhook-Timestamp",
    ) -> None:
        """Configure what signs, under which name and format.

        Args:
            algorithm: The digest the legacy signature is made with, named in the
                signature itself so a receiver knows what to recompute. The
                Standard Webhooks signature is always SHA-256; the scheme fixes it.
            signature_header_name: The header the signatures go in.
            signature_format: Which signatures to emit. The string a configuration
                carries is accepted.
            timestamp_header_name: The header the signed timestamp is read back
                from, which
                :class:`HeadersConfigurator <xtr_webhook.server.HeadersConfigurator>`
                must have written under the same name.

        Raises:
            InvalidArgumentError: When this runtime cannot make ``algorithm``, or
                when ``signature_format`` names no format. Both are caught here
                rather than at the first delivery: a sender that cannot sign is
                misconfigured, and finding out mid-send means a webhook already on
                its way.
        """
        if algorithm not in hashlib.algorithms_available:
            raise InvalidArgumentError(f'The signing algorithm "{algorithm}" is not available.')

        self._algorithm = algorithm
        self._signature_header_name = signature_header_name
        self._signature_format = SignatureFormat.parse(signature_format)
        self._timestamp_header_name = timestamp_header_name

    @override
    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        """Sign ``request`` and write the signatures into its header.

        Args:
            event: The event being sent, whose name and id the legacy signature
                covers.
            secret: The receiving subscriber's secret.
            request: The request being built, whose body must already be set.

        Raises:
            InvalidArgumentError: When ``secret`` is empty. An empty key still
                signs, so this would otherwise send perfectly formed webhooks no
                receiver can accept.
            LogicError: When the body has not been set, or when a format that signs
                the timestamp runs before whatever writes it. Both are an order the
                chain was built in, not something a delivery can fix.
        """
        if not secret:
            raise InvalidArgumentError("A non-empty secret is required.")

        body = request.body
        if body is None:
            raise LogicError("The body must be set.")

        signatures: list[str] = []

        if self._signature_format is not SignatureFormat.STANDARD:
            # Name, id and body run together with nothing between them: the digest
            # covers exactly these bytes in this order, and a receiver rebuilds it
            # the same way.
            digest = hmac.new(
                secret.encode(),
                event.name.encode() + event.id.encode() + body,
                self._algorithm,
            )
            signatures.append(f"{self._algorithm}={digest.hexdigest()}")

        if self._signature_format is not SignatureFormat.LEGACY:
            timestamp = request.headers.get(self._timestamp_header_name)
            if timestamp is None:
                raise LogicError(
                    f'The "{self._timestamp_header_name}" header must be set when emitting a '
                    'Standard Webhooks signature; ensure "HeadersConfigurator" runs before this '
                    "configurator.",
                )

            signatures.append(sign(event.id, timestamp, body, secret))

        request.headers[self._signature_header_name] = " ".join(signatures)
