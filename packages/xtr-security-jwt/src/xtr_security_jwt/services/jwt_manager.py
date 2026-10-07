"""Mints a self-issued token for a user and reads a presented one back."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.encoder.header_aware_jwt_encoder_interface import (
    HeaderAwareJwtEncoderInterface,
)
from xtr_security_jwt.event.jwt_created_event import JwtCreatedEvent
from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent
from xtr_security_jwt.event.jwt_encoded_event import JwtEncodedEvent
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment

from .credentialed_token_interface import CredentialedTokenInterface
from .jwt_token_manager_interface import JwtTokenManagerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
    from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface

__all__ = ["JwtManager"]


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

    __slots__ = (
        "_audience",
        "_encoder",
        "_event_dispatcher",
        "_issuer",
        "_payload_enrichment",
        "_user_id_claim",
    )

    def __init__(  # noqa: PLR0913 -- a wiring constructor; each part shapes one behaviour
        self,
        encoder: JwtEncoderInterface,
        event_dispatcher: EventDispatcherInterface,
        user_id_claim: str,
        payload_enrichment: PayloadEnrichmentInterface | None = None,
        *,
        issuer: str,
        audience: Sequence[str] = (),
    ) -> None:
        """Mint tokens with ``encoder``, stamped with ``issuer``, announcing events.

        Every minted token is stamped with ``issuer`` as ``iss`` and, when
        ``audience`` is set, with those names as ``aud``; a presented token is
        checked against both, so one issued for another issuer or audience is
        refused as it is read back.

        ``issuer`` is therefore refused empty: an unnamed issuer would stamp
        nothing and accept a token carrying no ``iss`` at all. This is the point
        where a configured issuer read from the environment is finally a value,
        so it is where an empty one is caught.

        Raises:
            InvalidArgumentError: When ``issuer`` is empty, or when ``audience``
                is a single string. A bare string is a sequence of its own
                letters, so ``"api"`` would be read as three one-letter
                audiences.
        """
        if not issuer:
            raise InvalidArgumentError(
                "The issuer cannot be empty: every minted token is stamped with it and "
                "every presented token is checked against it.",
            )
        if isinstance(audience, str):
            raise InvalidArgumentError(
                "The audience is a sequence of audience names, not one name: a bare "
                f"string is read letter by letter. Write audience=({audience!r},).",
            )
        self._encoder = encoder
        self._event_dispatcher = event_dispatcher
        self._user_id_claim = user_id_claim
        self._issuer = issuer
        self._audience = tuple(audience)
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
        # The user's roles are authoritative: a caller's payload must not widen
        # them, so they are re-applied after the merge overwrites the seed.
        merged["roles"] = list(user.get_roles())
        self._add_user_identity(user, merged)
        self._payload_enrichment.enrich(user, merged)
        return await self._generate(user, merged)

    @override
    async def decode(self, token: TokenInterface) -> Mapping[str, object] | bool:
        """Read the claims out of a security ``token``, or ``False`` when it has none.

        The raw compact token is read back from the token's credentials — where
        the authenticator's own post-authentication token keeps it — so a token
        of another kind, which keeps none, reports no claims.

        Where :meth:`parse` raises on a token that cannot be read or that a
        listener rejects, this reports the same outcome as ``False``.
        """
        raw = token.get_credentials() if isinstance(token, CredentialedTokenInterface) else None
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
        self._check_issuer_and_audience(payload)
        event = JwtDecodedEvent(payload)
        _ = await self._event_dispatcher.dispatch(event)
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

    def _check_issuer_and_audience(self, payload: Mapping[str, object]) -> None:
        """Refuse a token issued for another issuer or audience.

        The issuer and audience judgement belongs to whoever reads the loaded
        payload, not to the signing provider: a token's ``iss`` must equal the
        configured issuer, and — when audiences are configured — its ``aud`` must
        name at least one of them. A deployment configuring no audience
        identifies itself with none, so a token that names one is refused rather
        than read: RFC 7519 has a reader refuse a token whose audience it does
        not answer to.

        Raises:
            JwtDecodeFailureError: When the issuer differs, when no configured
                audience is named, or when the token names an audience and none
                is configured.
        """
        if payload.get("iss") != self._issuer:
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                "The token was issued for another issuer.",
                payload=payload,
            )
        if not self._audience and "aud" in payload:
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                "The token names an audience, and this deployment answers to none.",
                payload=payload,
            )
        if self._audience and not self._audience_matches(payload.get("aud")):
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                "The token was issued for another audience.",
                payload=payload,
            )

    def _audience_matches(self, claimed: object) -> bool:
        """Tell whether ``claimed`` names at least one configured audience."""
        if isinstance(claimed, str):
            names: tuple[str, ...] = (claimed,)
        elif isinstance(claimed, (list, tuple)):
            members: tuple[object, ...] = tuple(cast("tuple[object, ...]", claimed))
            names = tuple(one for one in members if isinstance(one, str))
        else:
            return False
        return any(one in self._audience for one in names)

    async def _generate(self, user: UserInterface, payload: dict[str, object]) -> str:
        """Announce, sign and announce again, returning the finished token."""
        payload["iss"] = self._issuer
        if self._audience:
            payload["aud"] = list(self._audience)
        created = JwtCreatedEvent(payload, user)
        _ = await self._event_dispatcher.dispatch(created)
        data = created.get_data()
        header = created.get_header()
        # The header-aware interface only widens ``encode``; the two protocols
        # overlap by design, so the runtime check is the intended one.
        if isinstance(self._encoder, HeaderAwareJwtEncoderInterface):  # pyright: ignore[reportGeneralTypeIssues]
            token = self._encoder.encode(data, header)
        else:
            token = self._encoder.encode(data)
        _ = await self._event_dispatcher.dispatch(JwtEncodedEvent(token))
        return token
