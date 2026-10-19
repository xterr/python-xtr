"""Recording the end of the session an OIDC provider says has ended."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging_contracts import NullLogger
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from xtr_logging_contracts import LoggerInterface

    from .oidc_discovery import OidcDiscovery
    from .oidc_ended_sessions import OidcEndedSessions
    from .oidc_logout_token import OidcLogoutToken
    from .oidc_signature_verifier import OidcSignatureVerifier

__all__ = ["OidcBackChannelLogout"]


@final
class OidcBackChannelLogout:
    """Records the end of the session an OIDC provider says has ended.

    The end arrives on the logout token the provider pushed. Nothing of the
    end-user is ended here: the request comes from the
    provider and carries nothing of the browser that logged in, not even its
    session cookie. It is the token of that browser that is refused on its
    next request, by the back-channel logout listener.

    A token naming a session this application never opened is not an error,
    and neither is one naming a session that already ended: both are
    recorded and cost nothing, and a provider telling a client about a
    session that client never opened looks like either.
    """

    __slots__ = (
        "_client_id",
        "_discovery",
        "_ended_sessions",
        "_logger",
        "_logout_token",
        "_signature_verifier",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the verifier, the claim reader, the discovery, the client and the store
        self,
        signature_verifier: OidcSignatureVerifier,
        logout_token: OidcLogoutToken,
        discovery: OidcDiscovery,
        client_id: str,
        ended_sessions: OidcEndedSessions,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record what verifies and reads a pushed logout token, and where its session end goes.

        Args:
            signature_verifier: Verifies the logout token's signature
                against the provider JWKS — the one check that makes the
                token the provider's, which the public endpoint this serves
                can never skip.
            logout_token: Validates the claims of the verified token.
            discovery: Reads the issuer the claims are validated against.
            client_id: The client the logout token must be intended for.
            ended_sessions: Where the ended session is written down.
            logger: Writes the refusals, when given.
        """
        self._signature_verifier = signature_verifier
        self._logout_token = logout_token
        self._discovery = discovery
        self._client_id = client_id
        self._ended_sessions = ended_sessions
        self._logger = logger or NullLogger()

    async def logout(self, logout_token: str) -> None:
        """Verify the given logout token and record that the session it names has ended.

        Raises:
            AuthenticationError: When the token is not one the provider
                issued, or does not say which session ended.
        """
        # nothing of the token is the provider's until its signature says so
        try:
            claims = await self._signature_verifier.verify(logout_token)
        except AuthenticationError as error:
            self._logger.warning(
                "The back-channel logout token could not be verified.",
                {"exception": error},
            )
            # the reason is logged rather than answered: the endpoint is
            # reachable by anyone, and the verifier names what it verifies
            # after the ID token it is built for, which a logout token is not
            raise AuthenticationError("The logout token could not be verified.") from error

        try:
            issuer = (await self._discovery.get_configuration()).get("issuer")
            sid = self._logout_token.validate_claims(
                claims,
                issuer if isinstance(issuer, str) else "",
                self._client_id,
            )
        except AuthenticationError as error:
            self._logger.warning(
                "The back-channel logout token was refused.",
                {"exception": error},
            )
            raise

        await self._ended_sessions.record(sid)
