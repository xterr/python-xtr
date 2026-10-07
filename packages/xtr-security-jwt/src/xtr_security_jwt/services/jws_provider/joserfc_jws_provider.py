"""Signs and verifies tokens with joserfc, over a key loader's material."""

from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING, cast, final

from joserfc import jws, jwt
from joserfc.errors import JoseError
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader._algorithms import (
    HMAC_ALGORITHMS,
    key_type_for_algorithm,
)
from xtr_security_jwt.services.key_loader.key_loader_interface import TYPE_PRIVATE, TYPE_PUBLIC
from xtr_security_jwt.signature.created_jws import CreatedJws
from xtr_security_jwt.signature.loaded_jws import LoadedJws

from ._key_material import (
    import_additional_keys,
    import_key,
    require_hmac_secret_length,
)
from .jws_provider_interface import JwsProviderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from joserfc.jwk import Key
    from xtr_clock import ClockInterface

    from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

__all__ = ["JoserfcJwsProvider", "require_hmac_secret_length"]


@final
class JoserfcJwsProvider(JwsProviderInterface):
    """Signs a payload and verifies a token with joserfc and one algorithm.

    The registered time claims are stamped as the reference does: ``iat`` is the
    payload's own value or the clock's now; ``exp`` is stamped only when a
    time-to-live is set or the payload already carries one, so a provider with no
    ttl and a payload without ``exp`` mints a token that never expires — which the
    verifier honours only when the deployment allows tokens without an expiry. An
    expiry a token does carry is judged either way. The clock skew is spent at
    verification, never at signing.

    A token naming a ``kid`` is verified against the key indexed under that id;
    failing that, the signing key's public half is tried first and then every
    additional public key, so a deployment rotating keys keeps accepting tokens
    signed by the keys it still trusts. Only the one configured algorithm is ever
    accepted, so a token presenting any other — ``none`` included — is refused
    before its signature is considered.
    """

    __slots__ = (
        "_allow_no_expiration",
        "_clock",
        "_clock_skew",
        "_key_loader",
        "_signature_algorithm",
        "_signing_key_cache",
        "_ttl",
        "_verifying_keys_by_kid",
        "_verifying_keys_cache",
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
        # The keys are imported once, on first use, and kept: a verify never
        # reads a key file again, and a token naming a ``kid`` finds its key by
        # that id rather than trying every trusted key in turn.
        self._signing_key_cache: Key | None = None
        self._verifying_keys_cache: list[Key] | None = None
        self._verifying_keys_by_kid: dict[str, Key] = {}

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
            InvalidArgumentError: When the token is not a readable compact JWS,
                or an additional public key this deployment trusts cannot be read.
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
        kid = header.get("kid")
        is_verified = self._verify(token, kid if isinstance(kid, str) else None)
        return LoadedJws(
            payload,
            self._clock,
            is_verified=is_verified,
            allow_no_expiration=self._allow_no_expiration,
            header=header,
            clock_skew=self._clock_skew,
        )

    def _verify(self, token: str, kid: str | None) -> bool:
        """Tell whether ``token`` verifies against a key this provider trusts.

        A token naming a ``kid`` is tried against the key that id names first —
        an O(1) lookup over the index every trusted key is filed in, which
        settles a rotating deployment in one attempt. A keyed miss is no proof
        the token is unsigned by a trusted key, because material naming no id —
        a lone PEM given as text — is indexed under none, so the trusted keys are
        then tried in turn anyway.
        """
        keys = self._verifying_keys()
        if kid is not None:
            keyed = self._verifying_keys_by_kid.get(kid)
            if keyed is not None and self._verifies_with(token, keyed):
                return True
        return any(self._verifies_with(token, key) for key in keys)

    def _verifies_with(self, token: str, key: Key) -> bool:
        """Tell whether ``token`` verifies against the single ``key``."""
        try:
            _ = jwt.decode(token, key, algorithms=[self._signature_algorithm])
        except (JoseError, ValueError):
            return False
        return True

    def _signing_key(self) -> Key:
        """Import the private key the configured algorithm signs with.

        Raises:
            InvalidArgumentError: When the key cannot be read as one of the
                algorithm's type.
        """
        if self._signing_key_cache is None:
            self._signing_key_cache = self._import(self._key_loader.load_key(TYPE_PRIVATE))
        return self._signing_key_cache

    def _verifying_keys(self) -> list[Key]:
        """Import the verifying key and every additional public key, indexing them by id.

        A shared secret verifies with the same key it signs with, so the private
        material is read for HMAC; an asymmetric key verifies with its public
        half. The keys are imported once and kept, so a later verify reads no key
        file, and each is filed under the ``kid`` it carries or, failing that, the
        id its source names it by — the loader's own id for the main key, the
        file's name for an extra.

        Raises:
            InvalidArgumentError: When an additional public key cannot be read.
                A deployment that named a key file means it to be trusted, so an
                unreadable one is reported rather than quietly dropped.
        """
        if self._verifying_keys_cache is not None:
            return self._verifying_keys_cache
        keys: list[Key] = []
        verifying_type = (
            TYPE_PRIVATE if self._signature_algorithm in HMAC_ALGORITHMS else TYPE_PUBLIC
        )
        with suppress(InvalidArgumentError):  # a verifier may hold extras only
            main = self._import(self._key_loader.load_key(verifying_type))
            keys.append(main)
            self._index(main, self._key_loader.get_key_id())
        passphrase = self._key_loader.get_passphrase()
        for extra in self._key_loader.get_additional_public_keys():
            for key in import_additional_keys(extra, self._signature_algorithm, passphrase):
                keys.append(key)
                self._index(key, extra.key_id)
        self._verifying_keys_cache = keys
        return keys

    def _index(self, key: Key, key_id: str | None) -> None:
        """File ``key`` under the id it carries, or under ``key_id`` when it carries none."""
        named = key.kid or key_id
        if named:
            _ = self._verifying_keys_by_kid.setdefault(named, key)

    def _import(self, material: str) -> Key:
        """Import ``material`` as the single key of the algorithm's type.

        Raises:
            InvalidArgumentError: When the material cannot be read as such a key.
            InvalidConfigurationError: When an HMAC secret is shorter than the
                algorithm requires.
        """
        return import_key(
            material,
            self._signature_algorithm,
            self._key_loader.get_passphrase(),
        )
