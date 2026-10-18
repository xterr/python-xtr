"""What starts a fresh authentication for a caller who is already authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["ReAuthenticationEntryPointInterface"]


@runtime_checkable
class ReAuthenticationEntryPointInterface(Protocol):
    """Starts a fresh authentication for a user who is already authenticated.

    This is deliberately not an
    :class:`~xtr_security_http.entry_point.authentication_entry_point_interface.AuthenticationEntryPointInterface`:
    that one answers "who are you?", and an existing session already satisfies
    it, so reusing it would send the caller to a login page that lets them
    straight back through. Here the caller is known, and the only thing being
    asked for is a fresh proof that they still hold their credentials — which
    is why the token is passed rather than an error.

    An entry point may implement this beside its own contract, in which case
    the firewall uses it for both without any extra configuration.

    Pairs with the recency attributes
    :attr:`~xtr_security_core.authorization.voter.authenticated_voter.AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY`
    and
    :attr:`~xtr_security_core.authorization.voter.authenticated_voter.AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY`,
    and with the
    :attr:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE`
    key the listener parks the asked attribute under.
    """

    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        """Return the response that asks the holder of ``token`` to prove themselves again.

        Args:
            request: The request a recency check refused.
            token: The token the caller already holds, so the fresh proof is
                asked of a known caller, not an anonymous one.
        """
        ...
