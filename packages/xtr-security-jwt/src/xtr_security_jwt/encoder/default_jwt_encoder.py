"""The default encoder, mapping a JWS provider's outcome to failure reasons."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.exception.jwt_encode_failure_error import JwtEncodeFailureError

from .header_aware_jwt_encoder_interface import HeaderAwareJwtEncoderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface

__all__ = ["DefaultJwtEncoder"]


@final
class DefaultJwtEncoder(HeaderAwareJwtEncoderInterface):
    """Signs and verifies through a JWS provider, translating its outcome.

    Signing that the provider refuses for a bad key or algorithm becomes a
    :class:`~xtr_security_jwt.exception.JwtEncodeFailureError` with the
    ``invalid_config`` reason, and a token the provider returned unsigned becomes
    one with ``unsigned_token``. Reading a token back turns the loaded token's
    state into the matching decode reason. The signature is judged first: a token
    whose signature does not verify is ``unverified_token`` and no payload is
    attached to the failure, so an unsigned or tampered token never leaks its
    claims and is never reported as merely expired. Only once the signature holds
    are the times judged — a future-dated or otherwise malformed token is
    ``invalid_token`` and an expired one is ``expired_token`` — and those failures
    carry the verified payload.
    """

    __slots__ = ("_jws_provider",)

    def __init__(self, jws_provider: JwsProviderInterface) -> None:
        """Sign and verify through ``jws_provider``."""
        self._jws_provider = jws_provider

    @override
    def encode(
        self,
        data: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> str:
        """Sign ``data`` into a token, carrying ``header``.

        Raises:
            JwtEncodeFailureError: When the signing configuration cannot sign, or
                the provider returned an unsigned token.
        """
        try:
            created = self._jws_provider.create(data, header)
        except InvalidArgumentError as error:
            raise JwtEncodeFailureError(
                JwtEncodeFailureError.INVALID_CONFIG,
                f"The token could not be signed: {error}",
            ) from error
        if not created.is_signed():
            raise JwtEncodeFailureError(
                JwtEncodeFailureError.UNSIGNED_TOKEN,
                "The provider returned an unsigned token.",
            )
        return created.get_token()

    @override
    def decode(self, token: str) -> Mapping[str, object]:
        """Read ``token`` back into its claims.

        Raises:
            JwtDecodeFailureError: When the token cannot be read, has expired, or
                its signature does not verify.
        """
        try:
            loaded = self._jws_provider.load(token)
        except Exception as error:
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                f"The token could not be read: {error}",
            ) from error
        if not loaded.is_verified():
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.UNVERIFIED_TOKEN,
                "The token signature could not be verified.",
            )
        if loaded.is_invalid():
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.INVALID_TOKEN,
                "The token is invalid.",
                payload=loaded.get_payload(),
            )
        if loaded.is_expired():
            raise JwtDecodeFailureError(
                JwtDecodeFailureError.EXPIRED_TOKEN,
                "The token has expired.",
                payload=loaded.get_payload(),
            )
        return loaded.get_payload()
