"""Introspects a bearer token on the authorization server that issued it."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from typing import TYPE_CHECKING, Final, final

from xtr_clock import SystemClock
from xtr_logging_contracts import EXCEPTION_KEY, NullLogger
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

from ._introspected_user import build_user
from ._introspection_claims import numeric_seconds, user_identifier, verify_members
from ._signed_response import verify_signed_response

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from joserfc._keys import KeySetSerialization
    from joserfc.jwk import KeySet
    from xtr_cache_contracts import CacheInterface, Callback, ItemInterface
    from xtr_clock import ClockInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.user.oauth2_user import OAuth2User

    from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

    Introspection = tuple[dict[str, object], bool]
    """The members of an introspection response, and whether they were read from a signed one."""

__all__ = ["Oauth2TokenHandler"]

_JWT_RESPONSE_MEDIA_TYPE: Final = "application/token-introspection+jwt"
"""RFC 9701 Section 5: the media type of a JWT introspection response."""

_METADATA_PATH: Final = "/.well-known/oauth-authorization-server"
"""RFC 8414 Section 3: the well-known path of the authorization server metadata."""


@final
class Oauth2TokenHandler:
    """Turns a bearer token into a user badge by introspecting it on the authorization server.

    The token is validated the only way a resource server can trust one it
    did not issue: it asks the authorization server (RFC 7662). The endpoint
    is reached by posting to the HTTP client the handler is given, which
    carries where the authorization server lives and how this resource server
    authenticates there — a scoped client declaring the introspection endpoint
    as its ``base_uri`` and its credentials as ``auth_basic`` is all RFC 7662
    Section 2.1 asks for. Nothing of that transport is described here.

    What is described here is what the resource server expects of the answer.
    The members that qualify the token are confronted with those expectations
    before a user badge is built from them: an authorization server that
    reports a token as active while dating it in the past or the future, or
    while naming another issuer or another audience, has described a token
    this resource server must not honor. Only ``active``, ``exp``, ``nbf``,
    ``iat``, ``iss`` and ``aud`` are read — the last two only when this
    resource server declares which ones it expects.

    The badge carries the identifier — read from ``claim``, or from ``sub``
    with ``username`` falling back — a loader that builds the
    :class:`~xtr_security_core.user.oauth2_user.OAuth2User` the response
    describes, and the members themselves as the badge's attributes, so the
    access-token authenticator reads the granted ``scope`` (or ``scp``) out of
    them. Every failure becomes an
    :class:`~xtr_security_http.exception.InvalidAccessTokenError`.

    The introspection responses of active tokens may be cached — see
    :meth:`enable_cache` — and asked back as a signed JWT — see
    :meth:`enable_signed_response`.
    """

    __slots__ = (
        "_allowed_time_drift",
        "_audiences",
        "_cache",
        "_cache_key_prefix",
        "_cache_ttl",
        "_claim",
        "_client",
        "_clock",
        "_enforce_signed_response",
        "_issuer",
        "_logger",
        "_metadata",
        "_metadata_cache",
        "_metadata_cache_key",
        "_metadata_client",
        "_signature_algorithms",
        "_signature_keyset",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the client, the logger and the five knobs it takes
        self,
        client: HttpClientInterface,
        logger: LoggerInterface | None = None,
        audiences: str | Sequence[str] = (),
        issuer: str | None = None,
        claim: str | None = None,
        clock: ClockInterface | None = None,
        allowed_time_drift: int = 0,
    ) -> None:
        """Record the client, the logger and what this resource server expects of a token.

        Args:
            client: The client the introspection endpoint is reached with,
                whose base URI is that endpoint and whose options carry the
                credentials of this resource server.
            logger: Writes the failures the authorization server's answer
                explains, when given.
            audiences: The identifiers of this resource server, one of which
                the ``aud`` of the introspection response must name, or an
                empty sequence to skip that check.
            issuer: The identifier of the authorization server, checked
                against the ``iss`` of the introspection response, or ``None``
                to skip that check.
            claim: The claim holding the user identifier, or ``None`` to read
                ``sub`` and fall back to ``username``.
            clock: What the time claims are confronted with.
            allowed_time_drift: The tolerance, in seconds, on the ``iat``,
                ``nbf`` and ``exp`` the authorization server reports.

        Raises:
            InvalidArgumentError: When an audience is not a non-empty string.
        """
        audience_list = (audiences,) if isinstance(audiences, str) else tuple(audiences)
        for value in audience_list:
            if not isinstance(value, str) or not value:  # pyright: ignore[reportUnnecessaryIsInstance] -- the annotation promises strings; a configuration written by hand is checked where it would cost a request
                raise InvalidArgumentError(
                    "The audiences of an OAuth2 token handler must be a non-empty string "
                    "or a sequence of non-empty strings.",
                )
        self._client = client
        self._logger = logger or NullLogger()
        self._audiences = audience_list
        self._issuer = issuer
        self._claim = claim
        self._allowed_time_drift = allowed_time_drift
        self._clock = clock if clock is not None else SystemClock()
        self._cache: CacheInterface | None = None
        self._cache_key_prefix = ""
        self._cache_ttl = 0
        self._signature_algorithms: tuple[str, ...] = ()
        self._signature_keyset: KeySet | None = None
        self._enforce_signed_response = True
        self._metadata: OidcDiscovery | None = None
        self._metadata_cache: CacheInterface | None = None
        self._metadata_cache_key: str | None = None
        self._metadata_client: HttpClientInterface | None = None

    def enable_cache(self, cache: CacheInterface, cache_key_prefix: str, ttl: int = 60) -> None:
        """Cache the introspection responses of active tokens, for at most ``ttl`` seconds.

        RFC 7662 Section 4 leaves the trade-off to the resource server: a
        longer lifetime spares the authorization server a round trip per
        request, at the cost of a window during which a revoked token is still
        accepted here. Two bounds are not left to the caller. No entry outlives
        the ``exp`` the authorization server reported, which that section
        makes a MUST NOT, and the response of an inactive token is not cached
        at all, so that arbitrary token values cannot be used to fill the
        pool.

        An entry is keyed by the digest of the token rather than by the token
        itself, so that a pool an operator, a backup or a neighbouring
        application can read holds no usable credential.

        Args:
            cache: The cache the responses are kept in.
            cache_key_prefix: What every key of this handler starts with, so
                one pool can serve several handlers.
            ttl: How many seconds an entry lives at most.

        Raises:
            InvalidArgumentError: When ``ttl`` is not a positive number of
                seconds.
        """
        if ttl <= 0:
            raise InvalidArgumentError(
                "The introspection cache lifetime must be a positive number of "
                f"seconds, {ttl} given.",
            )
        self._cache = cache
        self._cache_key_prefix = cache_key_prefix
        self._cache_ttl = ttl

    def enable_signed_response(
        self,
        algorithms: Sequence[str],
        keyset: KeySet | None = None,
        enforce: bool = True,
    ) -> None:
        """Request a JWT introspection response and verify its signature, as RFC 9701 defines it.

        The keys the response is verified against are the ``keyset`` given
        here, or the ones the authorization server's metadata publishes when
        :meth:`enable_signed_response_discovery` was called and no key set
        was pinned. Which algorithms this resource server accepts stays its
        own decision either way, so that an authorization server cannot widen
        it by announcing more.

        Args:
            algorithms: The signature algorithms allowed, never empty — the
                JOSE library reads an empty allow-list as no restriction.
            keyset: The keys the response is verified against, or ``None``
                to read them from the authorization server's metadata.
            enforce: Whether a plain JSON response must be refused once the
                authorization server is expected to sign the introspection
                response.

        Raises:
            InvalidArgumentError: When ``algorithms`` is empty.
            ImportError: When joserfc, which verifies the responses, is not
                installed — the ``oidc`` extra carries it.
        """
        if not algorithms:
            raise InvalidArgumentError(
                "Verifying signed introspection responses needs at least one allowed algorithm.",
            )
        if find_spec("joserfc") is None:  # pragma: no cover -- the extra carries it
            raise ImportError(
                "Verifying signed introspection responses needs joserfc; install the "
                "'oidc' extra: uv add \"xtr-security-http[oidc]\".",
            )
        self._signature_algorithms = tuple(algorithms)
        self._signature_keyset = keyset
        self._enforce_signed_response = enforce

    def enable_signed_response_discovery(
        self,
        cache: CacheInterface,
        client: HttpClientInterface,
        cache_key: str,
    ) -> None:
        """Read the verifying keys from the authorization server's metadata.

        RFC 8414 Section 3 builds the metadata URL by inserting the well-known
        path between the host and the path of the issuer identifier, where
        OIDC Discovery 1.0 appends it, so the URL is built here and handed to
        the discovery reader already absolute. The document is the authority
        for the ``jwks_uri`` only: which algorithms this resource server
        accepts stays its own decision, so that an authorization server cannot
        widen it by announcing more.

        The metadata document is kept under ``cache_key`` suffixed with
        ``.document``, and the keys under the bare ``cache_key``, for as long
        as the response headers' freshness arithmetic leaves, capped at what
        the JWKS reader allows.

        Args:
            cache: Where the metadata document and the keys are kept.
            client: The client the metadata document and the keys are fetched
                with.
            cache_key: What the entries' keys start with, so one pool can
                serve several handlers.

        Raises:
            BadMethodCallError: When no ``issuer`` was given to the
                constructor, since RFC 8414 Section 3 derives the metadata
                URL from it.
            ImportError: When joserfc, which verifies the responses, is not
                installed — the ``oidc`` extra carries it.
        """
        from xtr_security_core.exception import (  # noqa: PLC0415 -- the discovery reader rides the oidc extra
            BadMethodCallError,
        )

        from xtr_security_http.oidc.oidc_discovery import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcDiscovery,
        )

        if self._issuer is None:
            raise BadMethodCallError(
                'The "issuer" of the authorization server is required to read its '
                "metadata, since RFC 8414 Section 3 derives the metadata URL from it.",
            )
        if find_spec("joserfc") is None:  # pragma: no cover -- the extra carries it
            raise ImportError(
                "Verifying signed introspection responses needs joserfc; install the "
                "'oidc' extra: uv add \"xtr-security-http[oidc]\".",
            )
        self._metadata_cache = cache
        self._metadata_client = client
        self._metadata_cache_key = cache_key
        self._metadata = OidcDiscovery(
            client,
            cache,
            _metadata_url(self._issuer),
            self._issuer,
            cache_key=f"{cache_key}.document",
            checked_endpoints=("jwks_uri",),
        )

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Introspect ``access_token`` and return the badge naming its user.

        RFC 7662 Section 2.2 guarantees a single member on an inactive token,
        ``active``, and makes it a boolean, so it is the first one read and it
        is compared to true: nothing else states that the token can be used,
        the string ``"true"`` an authorization server may answer with least of
        all. The identifier claims are only looked up once that member has
        stated it.

        Anything the introspection throws is an answer the resource server
        could not read, so it turns into the bad credentials the firewall
        reports as a 401: a server that is unreachable, that refuses the
        caller, or that answers something other than the JSON object RFC 7662
        Section 2.2 defines says nothing about the token, and never that it is
        usable.

        Raises:
            InvalidAccessTokenError: When the authorization server does not
                vouch for the token, or its answer cannot be read.
        """
        try:
            return await self._badge_from(access_token)
        except InvalidAccessTokenError as error:
            self._log_failure(error)
            raise
        except Exception as error:
            self._log_failure(error)
            raise InvalidAccessTokenError(
                f"An error occurred on the authorization server: {error}",
            ) from error

    async def _badge_from(self, access_token: str) -> UserBadge:
        """Introspect the token, confront the answer, and build the badge.

        Raises:
            InvalidAccessTokenError: When the authorization server does not
                vouch for the token.
        """
        claims, signed = await self._introspect(access_token)
        if claims.get("active") is not True:
            raise InvalidAccessTokenError(
                'The claim "active" was not found on the authorization server '
                "response or is set to false.",
            )
        verify_members(
            claims,
            signed=signed,
            issuer=self._issuer,
            audiences=self._audiences,
            drift=self._allowed_time_drift,
            now=self._now(),
        )
        identifier = user_identifier(claims, self._claim)
        return UserBadge(
            identifier,
            user_loader=self._loader(claims),
            attributes=dict(claims),
        )

    async def _introspect(self, access_token: str) -> Introspection:
        """Return the members of the introspection response, from the cache when one holds them.

        The lifetime of an entry is the shorter of the configured one and of
        what the ``exp`` of the response leaves, and only the response of an
        active token is stored — see :meth:`enable_cache`.
        """
        if self._cache is None:
            return await self._request_introspection(access_token)
        key = f"{self._cache_key_prefix}{sha256(access_token.encode()).hexdigest()}"
        return await self._cache.get(key, self._introspection_for(access_token))

    def _introspection_for(self, access_token: str) -> Callback[Introspection]:
        """Return the callback that introspects and decides how long the answer is kept."""

        async def compute(item: ItemInterface) -> Introspection:
            claims, signed = await self._request_introspection(access_token)
            ttl = self._cache_ttl
            seconds = numeric_seconds(claims.get("exp"))
            if seconds is not None:
                ttl = min(ttl, int(seconds) - self._now())
            if ttl <= 0 or claims.get("active") is not True:
                # A zero lifetime is the cache contract's "do not keep": saving
                # the item removes whatever the pool held under its key.
                _ = item.expires_after(0)
            else:
                _ = item.expires_after(max(1, ttl))
            return claims, signed

        return compute

    async def _request_introspection(self, access_token: str) -> Introspection:
        """Call the introspection endpoint, and return the members it answered with.

        The request carries the token and the ``access_token`` hint of RFC 7662
        Section 2.1, and is posted to the base URI of the client, which is
        where the endpoint and the credentials of this resource server are
        configured. It asks for the media types it is able to read: a JWT
        introspection response is only ever served to a request announcing it,
        per RFC 9701 Section 4, and plain JSON is still offered alongside it
        when an unsigned response is tolerated, so that an authorization
        server that cannot sign answers instead of refusing the media type.
        The response headers are read before its body, so that the payload of
        a 4xx or a 5xx is never mistaken for an introspection response.

        Raises:
            InvalidAccessTokenError: When the answer is a JWT this resource
                server is not configured to verify, or a plain one where a
                signed one is required.
        """
        if not self._verifies_signed_responses():
            accept = "application/json"
        elif self._enforce_signed_response:
            accept = _JWT_RESPONSE_MEDIA_TYPE
        else:
            accept = f"{_JWT_RESPONSE_MEDIA_TYPE}, application/json"
        response = await self._client.request(
            "POST",
            "",
            headers={"Accept": accept},
            body={"token": access_token, "token_type_hint": "access_token"},
            max_redirects=0,
        )
        async with response:
            media_type = _media_type(response)
            if media_type == _JWT_RESPONSE_MEDIA_TYPE:
                if not self._verifies_signed_responses():
                    raise InvalidAccessTokenError(
                        "The authorization server returned a JWT introspection response, "
                        "which this resource server is not configured to verify.",
                    )
                members = verify_signed_response(
                    await response.get_content(),
                    keyset=await self._resolve_signature_keyset(),
                    algorithms=self._signature_algorithms,
                    issuer=self._issuer,
                    audiences=self._audiences,
                    drift=self._allowed_time_drift,
                    now=self._now(),
                )
                return members, True
            if self._verifies_signed_responses() and self._enforce_signed_response:
                raise InvalidAccessTokenError(
                    "A signed introspection response is required, but the authorization "
                    f'server answered with "{media_type or "no content type"}".',
                )
            return await response.to_array(), False

    def _loader(self, claims: Mapping[str, object]) -> Callable[[str], OAuth2User]:
        """Return the loader that builds the user the introspection response describes."""

        def load(identifier: str) -> OAuth2User:
            del identifier
            return build_user(claims)

        return load

    def _verifies_signed_responses(self) -> bool:
        """Tell whether this resource server can verify a signed response.

        It can when a key set was pinned, or when the authorization server's
        metadata was given to read one from.
        """
        return self._signature_keyset is not None or self._metadata is not None

    async def _resolve_signature_keyset(self) -> KeySet:
        """Return the keys a signed response is verified against.

        The pinned key set when one was given, or the one the authorization
        server publishes at the ``jwks_uri`` its metadata announces.
        """
        if self._signature_keyset is not None:
            return self._signature_keyset
        metadata_cache = self._metadata_cache
        metadata_client = self._metadata_client
        metadata = self._metadata
        # One of the two sources is set whenever a signed response is verified.
        if (
            metadata_cache is None or metadata_client is None or metadata is None
        ):  # pragma: no cover
            raise InvalidAccessTokenError(
                "A signed introspection response cannot be verified: no key set and "
                "no metadata to read one from.",
            )
        keys = await metadata_cache.get(
            self._metadata_cache_key or "",
            self._compute_metadata_keys,
        )
        return _key_set(keys)

    async def _compute_metadata_keys(self, item: ItemInterface) -> list[dict[str, object]]:
        """Fetch the verifying keys off the ``jwks_uri`` the metadata announces.

        The entry lives for what the response headers' freshness arithmetic
        leaves, capped at what the JWKS reader allows, or the default when the
        headers name nothing.
        """
        from xtr_security_http.oidc.oidc_jwks import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcJwks,
        )

        metadata = self._metadata
        metadata_client = self._metadata_client
        # The discovery path sets both.
        if metadata is None or metadata_client is None:  # pragma: no cover
            raise InvalidAccessTokenError(
                "A signed introspection response cannot be verified: no metadata to "
                "read the verifying keys from.",
            )
        jwks_uri = (await metadata.get_configuration()).get("jwks_uri")
        keys, ttl = await OidcJwks.from_response(
            await metadata_client.request(
                "GET",
                jwks_uri if isinstance(jwks_uri, str) else "",
                max_redirects=0,
            ),
            enforce_key_usage_verification=True,
            clock=self._clock,
        )
        _ = item.expires_after(min(ttl if ttl is not None else 3600, OidcJwks.MAX_TTL))
        return keys

    def _now(self) -> int:
        """Return the moment the clock reads, as a Unix timestamp."""
        return int(self._clock.now().timestamp())

    def _log_failure(self, error: Exception) -> None:
        """Write the failure the authorization server's answer explains."""
        self._logger.error(
            "An error occurred on the authorization server.",
            {"error": str(error), EXCEPTION_KEY: error},
        )


def _media_type(response: HttpResponseInterface) -> str:
    """Return the media type the response names, without its parameters.

    The parameters after ``;`` are dropped and the name is lower-cased, so the
    comparison holds whatever case and parameters the answer carried.
    """
    values = response.get_header("content-type")
    return (values[0] if values else "").split(";", 1)[0].strip().lower()


def _metadata_url(issuer: str) -> str:
    """Build the RFC 8414 Section 3 metadata URL of an issuer.

    The well-known path is inserted between the host component and the path
    of the issuer identifier, so one host can serve the metadata of several
    authorization servers.
    """
    from urllib.parse import (  # noqa: PLC0415 -- a stdlib import kept off the module head for the oidc-extra path
        urlsplit,
    )

    from xtr_security_core.exception import (  # noqa: PLC0415 -- the discovery reader rides the oidc extra
        BadMethodCallError,
    )

    parts = urlsplit(issuer.rstrip("/"))
    if not parts.scheme or not parts.hostname:
        raise BadMethodCallError(
            'The "issuer" of the authorization server must be an absolute URL to '
            f'read its metadata, "{issuer}" given.',
        )
    return f"{parts.scheme}://{parts.netloc}{_METADATA_PATH}{parts.path}"


def _key_set(keys: object) -> KeySet:
    """Turn the cached key dictionaries into the key set the verifier reads."""
    from typing import cast  # noqa: PLC0415 -- the cast target is a typing-only name

    from joserfc.jwk import (  # noqa: PLC0415 -- guarded behind the oidc extra
        KeySet as JoserfcKeySet,
    )

    serialization = cast("KeySetSerialization", cast("object", {"keys": keys}))
    return JoserfcKeySet.import_key_set(serialization)
