"""Signing an access token this application issues, as an ``at+jwt``."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from joserfc import jwt
from joserfc.jwk import KeyParameters, KeySet
from xtr_clock import SystemClock
from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_clock import ClockInterface

__all__ = ["OidcTokenGenerator"]


@final
class OidcTokenGenerator:
    """Signs an access token for a user of this application, as RFC 9068 profiles one.

    The token names the user — ``sub`` by default, or the claim configured —
    the audience it is minted for, the issuer that minted it, and, when a
    lifetime or a not-before is given, when it expires and when it starts.
    The header carries ``typ: at+jwt``, the type RFC 9068 Section 2.1 fixes
    for a JWT access token, so the token cannot be mistaken for the ID token
    an issuer mints for the same audience.

    The signature is made with a key of the key set that can sign under the
    chosen algorithm — one whose declared use is signing — and the algorithm
    and the issuer are each either named at every call or declared as the
    only one, so a token never leaves here carrying a value nobody chose.
    """

    __slots__ = ("_algorithms", "_audience", "_claim", "_clock", "_issuers", "_keyset")

    def __init__(  # noqa: PLR0913, PLR0917 -- the signing material, the allow-list and the three knobs a minted token carries
        self,
        algorithms: Sequence[str],
        keyset: KeySet,
        audience: str | Sequence[str],
        issuers: Sequence[str],
        claim: str = "sub",
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the signing material, the allow-list and what every minted token carries.

        Args:
            algorithms: The signature algorithms a token may be signed with,
                named as the JOSE library spells them.
            keyset: The keys a token is signed with; the one whose declared
                use is signing and that fits the algorithm is chosen.
            audience: The identifiers of the resource server the token is
                minted for; RFC 7519 Section 4.1.3 lets ``aud`` hold a single
                string or a list, and the single-string form is kept when one
                identifier is declared, the form providers emit.
            issuers: The identifiers this application minting tokens as; one
                of them becomes the token's ``iss``.
            claim: The claim carrying the user identifier.
            clock: What the token's ``iat`` is read from.

        Raises:
            InvalidArgumentError: When the audience is an empty list, or
                holds a value that is not a non-empty string.
        """
        audience_list = (audience,) if isinstance(audience, str) else tuple(audience)
        if not audience_list:
            raise InvalidArgumentError(
                "The audience of an OIDC token generator cannot be an empty list: "
                "a token minted for no resource server names no one.",
            )
        for value in audience_list:
            if not isinstance(value, str) or not value:  # pyright: ignore[reportUnnecessaryIsInstance] -- the annotation promises strings; a configuration written by hand is checked where it would cost a token
                raise InvalidArgumentError(
                    "The audience of an OIDC token generator must be a non-empty "
                    "string or a sequence of non-empty strings.",
                )
        self._algorithms = tuple(algorithms)
        self._keyset = keyset
        self._audience: str | list[str] = (
            audience_list[0] if len(audience_list) == 1 else list(audience_list)
        )
        self._issuers = tuple(issuers)
        self._claim = claim
        self._clock = clock if clock is not None else SystemClock()

    def generate(
        self,
        user_identifier: str,
        algorithm: str | None = None,
        issuer: str | None = None,
        ttl: int | None = None,
        not_before: datetime | None = None,
    ) -> str:
        """Sign the access token naming ``user_identifier``, and return it compact.

        Args:
            user_identifier: Who the token is for; it lands on the claim
                configured, ``sub`` by default.
            algorithm: The algorithm to sign with, or ``None`` for the only
                one declared.
            issuer: The issuer the token names, or ``None`` for the only one
                declared.
            ttl: How many seconds the token lives, or ``None`` for one that
                does not expire. Zero is read the same way, the issuer's own
                spelling of "no expiry".
            not_before: The moment the token starts being valid, or ``None``
                for one valid from the moment it is minted.

        Returns:
            The signed token, in the compact serialization.

        Raises:
            InvalidArgumentError: When the algorithm or the issuer is not one
                of the declared ones, or is not given while several are
                declared; when no key of the key set can sign under the
                algorithm; or when ``ttl`` is negative.
        """
        chosen = self._algorithm(algorithm)
        key = self._keyset.pick_random_key(chosen, KeyParameters(use="sig"))
        if key is None:
            raise InvalidArgumentError(f'No JWK found to sign with the "{chosen}" algorithm.')
        now = int(self._clock.now().timestamp())
        claims: dict[str, object] = {
            self._claim: user_identifier,
            "iat": now,
            "aud": self._audience,
            "iss": self._issuer(issuer),
        }
        if ttl:
            if ttl < 0:
                raise InvalidArgumentError("Time to live must be a positive integer.")
            claims["exp"] = now + ttl
        if not_before is not None:
            claims["nbf"] = int(not_before.timestamp())
        # The chosen algorithm is named as allowed: the JOSE library refuses
        # to sign with one outside its recommended set unless it is told the
        # caller chose it.
        return jwt.encode({"alg": chosen, "typ": "at+jwt"}, claims, key, algorithms=[chosen])

    def _algorithm(self, alias: str | None) -> str:
        """Return the algorithm to sign with: the one named, or the only one declared.

        Raises:
            InvalidArgumentError: When the algorithm named is not one of the
                declared ones, or none is named while not exactly one is
                declared.
        """
        if alias:
            if alias not in self._algorithms:
                raise InvalidArgumentError(
                    f'"{alias}" is not a valid algorithm. '
                    f'Available algorithms: "{self._joined(self._algorithms)}".',
                )
            return alias
        if len(self._algorithms) != 1:
            raise InvalidArgumentError(
                f"Please choose an algorithm. "
                f'Available algorithms: "{self._joined(self._algorithms)}".',
            )
        return self._algorithms[0]

    def _issuer(self, issuer: str | None) -> str:
        """Return the issuer the token names: the one given, or the only one declared.

        Raises:
            InvalidArgumentError: When the issuer given is not one of the
                declared ones, or none is given while not exactly one is
                declared.
        """
        if issuer:
            if issuer not in self._issuers:
                raise InvalidArgumentError(
                    f'"{issuer}" is not a valid issuer. '
                    f'Available issuers: "{self._joined(self._issuers)}".',
                )
            return issuer
        if len(self._issuers) != 1:
            raise InvalidArgumentError(
                f'Please choose an issuer. Available issuers: "{self._joined(self._issuers)}".',
            )
        return self._issuers[0]

    @staticmethod
    def _joined(values: Sequence[str]) -> str:
        """Join ``values`` the way a refusal lists them: quoted, comma-separated."""
        return '", "'.join(values)
