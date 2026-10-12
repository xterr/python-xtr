"""An access token signs itself into the JWT a resource server reads."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["RESERVED_CLAIMS", "AccessTokenTrait"]

#: The claim names the token mints itself. An extra claim may not take one of
#: them: a resource server decides on these, so letting a listener overwrite
#: the issuer or the expiry would let it hand out a token nobody meant to.
RESERVED_CLAIMS: Final[frozenset[str]] = frozenset(
    {"aud", "client_id", "exp", "iat", "iss", "jti", "nbf", "scope", "sub"},
)

#: What the header says a token is, so a resource server can refuse an
#: identity token presented as an access token (RFC 9068, Section 2.1).
_TYPE_HEADER: Final[str] = "at+jwt"

_NO_EXTRA_CLAIMS: Final[Mapping[str, object]] = MappingProxyType({})


class AccessTokenTrait:
    """Signs an access token into a self-describing JWT.

    Compose it with the identifier trait and the token-state trait and the
    entity is complete.

    The token follows the JWT access-token profile (RFC 9068): the header says
    ``at+jwt`` and names the key, and the claims say where the token came from
    (``iss``), who it is for (``sub``, the resource owner or, for a client
    acting for itself, the client), who should accept it (``aud``), which
    client asked (``client_id``), the window it is good for (``iat``, ``nbf``,
    ``exp``), what it is called (``jti``) and what it may do (``scope``). A
    resource server reading those decides on its own, without asking this
    server anything — which is the whole point of signing rather than storing.

    :meth:`set_private_key` keeps the name every grant calls it by, but what it
    takes is no longer a bare key: signing to the profile needs the issuer to
    claim, the audience to address and a clock besides the key, and those
    travel together as one
    :class:`~xtr_security_oauth2_server_core.entities.access_token_signer.AccessTokenSigner`.

    Extra claims may be added before signing, and there is no reader for them:
    they exist to be signed in, and :meth:`to_string` is what reads them.
    """

    _signer: AccessTokenSigner
    _extra_claims: Mapping[str, object] = _NO_EXTRA_CLAIMS

    if TYPE_CHECKING:
        # Declared for the type checker, never defined here: whatever composes
        # this trait brings them — the identifier trait and the token-state
        # trait do, and a mapped entity may bring its own — and at runtime each
        # name resolves to that.
        def get_identifier(self) -> str:
            """Return the identifier this token is named by."""
            ...

        def get_expiry_date_time(self) -> datetime:
            """Return the instant this token stops being accepted."""
            ...

        def get_user_identifier(self) -> str | None:
            """Return the resource owner this token is for, or ``None`` for none."""
            ...

        def get_client(self) -> ClientEntityInterface:
            """Return the client this token was issued to."""
            ...

        def get_scopes(self) -> Sequence[ScopeEntityInterface]:
            """Return the scopes this token carries."""
            ...

    def set_private_key(self, signer: AccessTokenSigner) -> None:
        """Hand this token the key, the names and the clock it signs itself with."""
        self._signer = signer

    def set_extra_claims(self, claims: Mapping[str, object]) -> None:
        """Carry ``claims`` in the signed token, besides the ones it mints.

        Raises:
            InvalidArgumentError: When a claim takes one of
                :data:`RESERVED_CLAIMS`, which the token decides itself.
        """
        taken = sorted(RESERVED_CLAIMS & claims.keys())
        if taken:
            raise InvalidArgumentError(
                f"The claims {taken} are minted by the access token itself and cannot be "
                "set as extra claims; name the extra claims something else.",
            )
        self._extra_claims = MappingProxyType(dict(claims))

    def to_string(self) -> str:
        """Return this token as the signed string a client is handed.

        Raises:
            InvalidArgumentError: When no signer was handed over, or when the
                provider answered with a token it had not signed.
        """
        signer = self._signer_or_fail()
        issued_at = int(signer.clock.now().timestamp())
        created = signer.jws_provider.create(
            self._claims(signer, issued_at),
            {"typ": _TYPE_HEADER, "kid": signer.key_id},
        )
        if not created.is_signed():
            raise InvalidArgumentError(
                "The signature provider answered with an unsigned access token, which no "
                "resource server may be handed; check the provider's algorithm and key.",
            )
        return created.get_token()

    def _claims(self, signer: AccessTokenSigner, issued_at: int) -> Mapping[str, object]:
        """Build the claims this token makes, the extra ones last."""
        client_identifier = self.get_client().get_identifier()
        user_identifier = self.get_user_identifier()
        return {
            "iss": signer.issuer,
            "sub": client_identifier if user_identifier is None else user_identifier,
            "aud": client_identifier if signer.audience is None else signer.audience,
            "client_id": client_identifier,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": int(self.get_expiry_date_time().timestamp()),
            "jti": self.get_identifier(),
            "scope": " ".join(scope.get_identifier() for scope in self.get_scopes()),
            **self._extra_claims,
        }

    def _signer_or_fail(self) -> AccessTokenSigner:
        """Return the signer this token was handed.

        Raises:
            InvalidArgumentError: When nothing handed it one, which means a
                token is about to be returned that nobody could verify.
        """
        try:
            return self._signer
        except AttributeError:
            raise InvalidArgumentError(
                "This access token has no signer, so it cannot be signed; hand it one "
                "with set_private_key before asking for its string form.",
            ) from None
