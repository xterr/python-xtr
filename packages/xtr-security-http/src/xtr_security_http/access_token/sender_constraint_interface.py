"""What a request has to prove about the token it presents, beyond holding it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["SenderConstraintInterface"]


@runtime_checkable
class SenderConstraintInterface(Protocol):
    """Tells whether a request presenting an access token proves possession of what it is bound to.

    A bearer token is accepted from whoever holds it. A sender-constrained
    one names a key or a certificate in its ``cnf`` claim (RFC 7800,
    Section 3.1), and is accepted only from a request that proves possession
    of it: DPoP does it with a signature over the request (RFC 9449), mutual
    TLS with the certificate of the handshake (RFC 8705, Section 3). The
    token handler says what the token is; this says whether the request
    carrying it is the one it was issued to.
    """

    async def check(
        self,
        request: ServerRequestInterface,
        access_token: str,
        claims: Mapping[str, object],
    ) -> None:
        """Weigh the request against what ``access_token`` says it is bound to.

        Args:
            request: The request presenting the token.
            access_token: The token the request presented.
            claims: The claims the token handler read from the access token —
                the ``cnf`` of RFC 7800, Section 3.1 among them.

        Raises:
            AuthenticationError: When the request does not prove possession
                of what the token is bound to.
        """
        ...

    def get_challenge(
        self,
        error: AuthenticationError | None,
    ) -> tuple[str, Mapping[str, str]]:
        """Answer the scheme this constraint's tokens are presented under, and its parameters.

        A resource server accepting sender-constrained tokens challenges
        with the scheme they are presented under, so a client is told how to
        come back rather than being sent to build a bearer request that would
        be refused again. The parameters override the ones the authenticator
        builds itself.

        Args:
            error: The failure being answered, or ``None`` when the request
                carried no access token at all.

        Returns:
            The authentication scheme the challenge names, and the parameters
            to add to its ``WWW-Authenticate`` header.
        """
        ...
