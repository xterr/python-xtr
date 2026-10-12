"""The parser for webhooks this library's own sender signs, in any of its three formats."""

from __future__ import annotations

import hmac
import re
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import Clock
from xtr_remote_event import RemoteEvent

from xtr_webhook._standard_webhooks_signature import sign
from xtr_webhook.exception import InvalidArgumentError, RejectWebhookError
from xtr_webhook.server.signature_format import SignatureFormat

from .abstract_request_parser import AbstractRequestParser
from .chain_request_matcher import ChainRequestMatcher
from .is_json_request_matcher import IsJsonRequestMatcher
from .method_request_matcher import MethodRequestMatcher

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from .request_matcher_interface import RequestMatcherInterface

__all__ = ["RequestParser"]

_UNACCEPTABLE: Final = 406

_NUMERIC: Final = re.compile(r"^-?\d+$")
"""What a timestamp this parser can bound looks like: an integer, nothing else."""


@final
class RequestParser(AbstractRequestParser):
    """Reads webhooks signed the way this library's own sender signs them.

    The mirror of the sender's configurators: the same two signature schemes,
    under the same default header names, chosen by the same
    :class:`SignatureFormat <xtr_webhook.server.SignatureFormat>`. Under the
    transitional format either scheme authenticates a request, which is what
    lets the two ends migrate on different days.

    The signature header may carry several whitespace-separated entries — one
    per secret during a rotation — and any one that verifies is enough. When a
    Standard Webhooks entry verifies, the timestamp it covers is then held to a
    window around now, so a delivery captured once cannot be fed back later.
    """

    def __init__(  # noqa: PLR0913, PLR0917 — every name and bound has a default both ends share.
        self,
        algorithm: str = "sha256",
        signature_header_name: str = "Webhook-Signature",
        event_header_name: str = "Webhook-Event",
        id_header_name: str = "Webhook-Id",
        timestamp_header_name: str = "Webhook-Timestamp",
        signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
        timestamp_tolerance: int = 300,
        clock: ClockInterface | None = None,
    ) -> None:
        """Configure what to verify against, under which names and bounds.

        Args:
            algorithm: The digest the legacy signature is recomputed with. The
                Standard Webhooks signature is always SHA-256; the scheme fixes it.
            signature_header_name: The header the signature entries arrive in.
            event_header_name: The header the event's name arrives in, where the
                format sends one.
            id_header_name: The header the event's id arrives in.
            timestamp_header_name: The header the signed timestamp arrives in.
            signature_format: Which scheme a request must carry. The string a
                configuration carries is accepted.
            timestamp_tolerance: How many seconds either side of now a signed
                timestamp may be. Zero or less turns the bound off — for a
                replayed capture to matter less than clocks that cannot be kept
                close enough.
            clock: What now is measured by. ``None`` reads whichever clock is in
                force when a request arrives, so a test can freeze it without
                rebuilding the parser.

        Raises:
            InvalidArgumentError: When ``signature_format`` names no format.
        """
        self._algorithm = algorithm
        self._signature_header_name = signature_header_name
        self._event_header_name = event_header_name
        self._id_header_name = id_header_name
        self._timestamp_header_name = timestamp_header_name
        self._signature_format = SignatureFormat.parse(signature_format)
        self._timestamp_tolerance = timestamp_tolerance
        self._clock = clock

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        """Claim only a ``POST`` carrying a JSON body, as the sender's side emits."""
        return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    @override
    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent:
        """Check that the request is genuine and read the one event it carries.

        Args:
            request: The request that arrived, already claimed by the matcher.
            secret: What the signature entries are checked against.

        Returns:
            The event, named by the payload's ``type`` key when the Standard
            Webhooks entry authenticated the request — that scheme signs no
            header, so a name sent as one cannot be trusted — and by the event
            header otherwise, which the legacy scheme does sign.

        Raises:
            InvalidArgumentError: When ``secret`` is empty. That is this side's
                configuration, not the sender's doing, so it surfaces as a
                server error rather than as a refusal.
            RejectWebhookError: When a required header is missing, no signature
                entry verifies, the signed timestamp is outside the window, or
                the payload names no event.
        """
        if not secret:
            raise InvalidArgumentError("A non-empty secret is required.")

        payload = self.read_json(request)

        required = [self._signature_header_name, self._id_header_name]
        if self._signature_format is SignatureFormat.LEGACY:
            required.append(self._event_header_name)
        elif self._signature_format is SignatureFormat.STANDARD:
            required.append(self._timestamp_header_name)

        for name in required:
            if not request.has_header(name):
                raise RejectWebhookError(
                    _UNACCEPTABLE, f'Missing "{name}" HTTP request signature header.'
                )

        verified = self._verify_signature(request, self.read_body(request), secret)

        return RemoteEvent(
            self._event_name(payload)
            if verified is SignatureFormat.STANDARD
            else request.get_header_line(self._event_header_name),
            request.get_header_line(self._id_header_name),
            payload,
        )

    def _verify_signature(
        self, request: ServerRequestInterface, body: bytes, secret: str
    ) -> SignatureFormat:
        """Return the scheme of the entry that authenticated the request.

        The header may carry several whitespace-separated entries, one per
        secret during a rotation. Each expectation is computed once, before its
        loop, so the number of entries a request carries does not drive the CPU
        cost of rejecting it; every comparison is :func:`hmac.compare_digest`,
        so the time one takes says nothing about how much of it was right.

        Args:
            request: The request that arrived.
            body: Its body, whole — the exact bytes the sender signed.
            secret: What the entries are checked against.

        Raises:
            RejectWebhookError: When no entry verifies, or when the one that did
                covers a timestamp outside the window.
        """
        candidates = request.get_header_line(self._signature_header_name).split()
        message_id = request.get_header_line(self._id_header_name)

        # The Standard Webhooks entry is tried first, so that a request carrying
        # both schemes is replay-bounded whatever order its entries arrive in.
        if self._signature_format is not SignatureFormat.LEGACY and request.has_header(
            self._timestamp_header_name
        ):
            timestamp = request.get_header_line(self._timestamp_header_name)
            expected = sign(message_id, timestamp, body, secret).encode()

            for candidate in candidates:
                if hmac.compare_digest(expected, candidate.encode()):
                    self._check_timestamp(timestamp)

                    return SignatureFormat.STANDARD

        if self._signature_format is not SignatureFormat.STANDARD and request.has_header(
            self._event_header_name
        ):
            event = request.get_header_line(self._event_header_name)
            digest = hmac.new(
                secret.encode(), event.encode() + message_id.encode() + body, self._algorithm
            )
            expected = f"{self._algorithm}={digest.hexdigest()}".encode()

            for candidate in candidates:
                if hmac.compare_digest(expected, candidate.encode()):
                    return SignatureFormat.LEGACY

        raise RejectWebhookError(_UNACCEPTABLE, "Signature is wrong.")

    def _check_timestamp(self, timestamp: str) -> None:
        """Refuse a signed timestamp outside the window around now.

        Run only after a Standard Webhooks entry verified, because only then is
        the timestamp known to be the sender's rather than an attacker's.

        Args:
            timestamp: What the timestamp header carried, already signed.

        Raises:
            RejectWebhookError: When the timestamp does not read as an integer —
                a value that cannot be bounded is not accepted on faith — or
                lies further than the tolerance from now.
        """
        if self._timestamp_tolerance <= 0:
            return

        now = int((self._clock or Clock.get()).now().timestamp())

        if (
            _NUMERIC.match(timestamp) is None
            or abs(now - int(timestamp)) > self._timestamp_tolerance
        ):
            raise RejectWebhookError(
                _UNACCEPTABLE,
                f'The "{self._timestamp_header_name}" HTTP request header is outside the '
                "accepted window.",
            )

    def _event_name(self, payload: dict[str, object]) -> str:
        """Return the event's name from the payload's ``type`` key.

        Args:
            payload: The body, already decoded.

        Raises:
            RejectWebhookError: When the key is missing or not a string — the
                scheme that signed this request puts the name there, so a
                payload without one names no event.
        """
        name = payload.get("type")
        if not isinstance(name, str):
            raise RejectWebhookError(
                _UNACCEPTABLE, 'The payload is missing the "type" key holding the event name.'
            )

        return name
