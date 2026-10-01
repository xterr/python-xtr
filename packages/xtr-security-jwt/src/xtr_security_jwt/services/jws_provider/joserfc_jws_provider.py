"""Signs and verifies tokens with joserfc, over a key loader's material."""

from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING, cast, final

from joserfc import jws, jwt
from joserfc.errors import JoseError
from joserfc.jwk import ECKey, OctKey, OKPKey, RSAKey
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader._algorithms import (
    HMAC_ALGORITHMS,
    key_type_for_algorithm,
)
from xtr_security_jwt.services.key_loader.key_loader_interface import TYPE_PRIVATE, TYPE_PUBLIC
from xtr_security_jwt.signature.created_jws import CreatedJws
from xtr_security_jwt.signature.loaded_jws import LoadedJws

from .jws_provider_interface import JwsProviderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface

    from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

__all__ = ["JoserfcJwsProvider"]

_Key = OctKey | RSAKey | ECKey | OKPKey

_PEM_KEY_CLASSES: dict[str, type[RSAKey | ECKey | OKPKey]] = {
    "RSA": RSAKey,
    "EC": ECKey,
    "OKP": OKPKey,
}


@final
class JoserfcJwsProvider(JwsProviderInterface):
    """Signs a payload and verifies a token with joserfc and one algorithm.

    The registered time claims are stamped as the reference does: ``iat`` is the
    payload's own value or the clock's now; ``exp`` is stamped only when a
    time-to-live is set or the payload already carries one, so a provider with no
    ttl and a payload without ``exp`` mints a token that never expires — which the
    verifier honours only when the deployment allows tokens without an expiry.
    The clock skew is spent at verification, never at signing.

    Verification tries the signing key's public half first, then every additional
    public key, so a deployment rotating keys keeps accepting tokens signed by the
    keys it still trusts. Only the one configured algorithm is ever accepted, so a
    token presenting any other — ``none`` included — is refused before its
    signature is considered.
    """

    __slots__ = (
        "_allow_no_expiration",
        "_clock",
        "_clock_skew",
        "_key_loader",
        "_signature_algorithm",
        "_ttl",
    )

    def __init__(  # noqa: PLR0913 -- a wiring constructor; each part shapes one behaviour
        self,
        key_loader: KeyLoaderInterface,
        signature_algorithm: str,
        ttl: int | None,
        clock_skew: int,
        clock: ClockInterface,
        *,
        allow_no_expiration: bool = False,
    ) -> None:
        """Sign and verify with ``key_loader``'s keys and ``signature_algorithm``.

        Raises:
            InvalidArgumentError: When ``signature_algorithm`` is not one this
                library signs or verifies with.
        """
        _ = key_type_for_algorithm(signature_algorithm)
        self._key_loader = key_loader
        self._signature_algorithm = signature_algorithm
        self._ttl = ttl
        self._clock_skew = clock_skew
        self._clock = clock
        self._allow_no_expiration = allow_no_expiration

    @override
    def create(
        self,
        payload: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> CreatedJws:
        """Sign ``payload`` into a token, stamping the registered time claims.

        Raises:
            InvalidArgumentError: When the signing key cannot be read as a key of
                the algorithm's type.
        """
        claims = dict(payload)
        now = int(self._clock.now().timestamp())
        if "iat" not in claims:
            claims["iat"] = now
        if self._ttl is not None and "exp" not in claims:
            claims["exp"] = now + self._ttl
        head: dict[str, object] = dict(header) if header is not None else {}
        head["alg"] = self._signature_algorithm
        key = self._signing_key()
        token = jwt.encode(
            head,
            claims,
            key,
            algorithms=[self._signature_algorithm],
        )
        return CreatedJws(token, is_signed=True)

    @override
    def load(self, token: str) -> LoadedJws:
        """Read ``token`` back, verifying its signature and judging its times.

        Raises:
            InvalidArgumentError: When the token is not a readable compact JWS.
        """
        try:
            extracted = jws.extract_compact(token.encode("utf-8"))
        except (JoseError, ValueError) as error:
            raise InvalidArgumentError(f"The token is not a readable JWS: {error}") from error
        header = dict(extracted.headers())
        try:
            decoded = cast("object", json.loads(extracted.payload))
        except (ValueError, UnicodeDecodeError) as error:
            raise InvalidArgumentError("The token payload is not readable JSON.") from error
        if not isinstance(decoded, dict):
            raise InvalidArgumentError("The token payload is not a JSON object.")
        payload = cast("dict[str, object]", decoded)
        is_verified = self._verify(token)
        return LoadedJws(
            payload,
            self._clock,
            is_verified=is_verified,
            should_check_expiration=not self._allow_no_expiration,
            header=header,
            clock_skew=self._clock_skew,
        )

    def _verify(self, token: str) -> bool:
        """Tell whether ``token`` verifies against a key this provider trusts."""
        for key in self._verifying_keys():
            try:
                _ = jwt.decode(token, key, algorithms=[self._signature_algorithm])
            except (JoseError, ValueError):
                continue
            return True
        return False

    def _signing_key(self) -> _Key:
        """Import the private key the configured algorithm signs with.

        Raises:
            InvalidArgumentError: When the key cannot be read as one of the
                algorithm's type.
        """
        material = self._key_loader.load_key(TYPE_PRIVATE)
        return self._import(material)

    def _verifying_keys(self) -> list[_Key]:
        """Import the verifying key and every additional public key, skipping bad ones.

        A shared secret verifies with the same key it signs with, so the private
        material is read for HMAC; an asymmetric key verifies with its public half.
        """
        keys: list[_Key] = []
        verifying_type = (
            TYPE_PRIVATE if self._signature_algorithm in HMAC_ALGORITHMS else TYPE_PUBLIC
        )
        with suppress(InvalidArgumentError):  # a misconfigured key set is skipped
            keys.append(self._import(self._key_loader.load_key(verifying_type)))
        for material in self._key_loader.get_additional_public_keys():
            try:
                keys.append(self._import(material))
            except InvalidArgumentError:  # pragma: no cover — a misconfigured extra key
                continue
        return keys

    def _import(self, material: str) -> _Key:
        """Import ``material`` as a key of the algorithm's type.

        Raises:
            InvalidArgumentError: When the material cannot be read as such a key.
        """
        if self._signature_algorithm in HMAC_ALGORITHMS:
            return OctKey.import_key(material)
        key_type = key_type_for_algorithm(self._signature_algorithm)
        key_class = _PEM_KEY_CLASSES[key_type]
        passphrase = self._key_loader.get_passphrase()
        password = passphrase.encode("utf-8") if passphrase else None
        try:
            return key_class.import_key(material, password=password)
        except (JoseError, ValueError, TypeError) as error:
            raise InvalidArgumentError(
                f"The key material could not be read as a {key_type} key: {error}",
            ) from error
