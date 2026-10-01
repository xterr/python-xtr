"""Mints a self-issued token for a user and reads a presented one back."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_jwt.encoder.header_aware_jwt_encoder_interface import (
    HeaderAwareJwtEncoderInterface,
)
from xtr_security_jwt.event.jwt_created_event import JwtCreatedEvent
from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent
from xtr_security_jwt.event.jwt_encoded_event import JwtEncodedEvent
from xtr_security_jwt.events import Events
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment

from .jwt_token_manager_interface import JwtTokenManagerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
    from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface

__all__ = ["JwtManager"]

#: The credentials attribute a security token carries the raw JWT under.
_TOKEN_ATTRIBUTE: str = "token"  # noqa: S105 -- an attribute name, not a secret


@final
class JwtManager(JwtTokenManagerInterface):
    """Assembles, announces and signs a token, and reads a presented one back.

    Minting starts from the user's roles and the claim naming who they are — read
    from the attribute the user-id claim names when the user carries one, else the
    user's identifier — then runs the payload enrichment, announces the claims and
    headers on a :class:`~xtr_security_jwt.event.jwt_created_event.JwtCreatedEvent`
    a listener may shape, signs through the encoder, and announces the finished
    token on a :class:`~xtr_security_jwt.event.jwt_encoded_event.JwtEncodedEvent`.
    None of the token is ever taken from client input.

    Reading a token back verifies it through the encoder and announces its payload
    on a :class:`~xtr_security_jwt.event.jwt_decoded_event.JwtDecodedEvent`, which
    a listener may reject.
    """

    __slots__ = ("_encoder", "_event_dispatcher", "_payload_enrichment", "_user_id_claim")

    def __init__(
        self,
        encoder: JwtEncoderInterface,
        event_dispatcher: EventDispatcherInterface,
        user_id_claim: str,
        payload_enrichment: PayloadEnrichmentInterface | None = None,
    ) -> None:
        """Mint tokens with ``encoder``, announcing on ``event_dispatcher``."""
        self._encoder = encoder
        self._event_dispatcher = event_dispatcher
        self._user_id_claim = user_id_claim
        self._payload_enrichment = (
            payload_enrichment if payload_enrichment is not None else NullEnrichment()
        )

    @override
    async def create(self, user: UserInterface) -> str:
        """Mint a signed token for ``user``, carrying its roles and identity."""
        payload: dict[str, object] = {"roles": list(user.get_roles())}
        self._add_user_identity(user, payload)
        self._payload_enrichment.enrich(user, payload)
        return await self._generate(user, payload)

    @override
    async def create_from_payload(
        self,
        user: UserInterface,
        payload: Mapping[str, object],
    ) -> str:
        """Mint a signed token for ``user``, starting from a caller's ``payload``."""
        merged: dict[str, object] = {"roles": list(user.get_roles())}
        merged.update(payload)
        self._add_user_identity(user, merged)
        self._payload_enrichment.enrich(user, merged)
        return await self._generate(user, merged)

    @override
    async def decode(self, token: TokenInterface) -> Mapping[str, object] | bool:
        """Read the claims out of a security ``token``, or ``False`` when it has none.

        Where :meth:`parse` raises on a token that cannot be read or that a
        listener rejects, this reports the same outcome as ``False``.
        """
        raw = (
            token.get_attribute(_TOKEN_ATTRIBUTE) if token.has_attribute(_TOKEN_ATTRIBUTE) else None
        )
        if not isinstance(raw, str) or not raw:
            return False
        try:
            return await self.parse(raw)
        except JwtDecodeFailureError:
            return False

    @override
    async def parse(self, token: str) -> Mapping[str, object]:
        """Verify a compact ``token``, announce its payload, and return it.

        Raises:
            JwtDecodeFailureError: When the token cannot be read or a listener
                rejects it.
        """
        payload = dict(self._encoder.decode(token))
        event = JwtDecodedEvent(payload)
        _ = await self._event_dispatcher.dispatch(event, Events.JWT_DECODED)
        if not event.is_valid():
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                "The token was rejected while decoding.",
                payload=event.get_payload(),
            )
        return event.get_payload()

    @override
    def get_user_id_claim(self) -> str:
        """Return the claim the user's identifier is written into."""
        return self._user_id_claim

    def _add_user_identity(self, user: UserInterface, payload: dict[str, object]) -> None:
        """Write the user's identity into the payload under the user-id claim."""
        value = getattr(user, self._user_id_claim, None)
        if not isinstance(value, str) or not value:
            value = user.get_user_identifier()
        payload[self._user_id_claim] = value

    async def _generate(self, user: UserInterface, payload: dict[str, object]) -> str:
        """Announce, sign and announce again, returning the finished token."""
        created = JwtCreatedEvent(payload, user)
        _ = await self._event_dispatcher.dispatch(created, Events.JWT_CREATED)
        data = created.get_data()
        header = created.get_header()
        # The header-aware interface only widens ``encode``; the two protocols
        # overlap by design, so the runtime check is the intended one.
        if isinstance(self._encoder, HeaderAwareJwtEncoderInterface):  # pyright: ignore[reportGeneralTypeIssues]
            token = self._encoder.encode(data, header)
        else:
            token = self._encoder.encode(data)
        _ = await self._event_dispatcher.dispatch(JwtEncodedEvent(token), Events.JWT_ENCODED)
        return token
