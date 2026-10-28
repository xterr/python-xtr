"""The base of the authenticators for a request already authenticated elsewhere.

A request can arrive already vouched for — the server in front of the
application authenticated it, a certificate named its user. The authenticators
for those requests share one shape: read the username the request carries as
already proven, load the user through the firewall's provider, and settle on
the token that records the firewall that read the identity. What each one
owns is the reading: where in the request the username lives, and what
carrying none of it looks like.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override
from xtr_security_core.authentication.token.pre_authenticated_token import PreAuthenticatedToken
from xtr_security_core.exception import BadCredentialsError

from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .passport.badge.pre_authenticated_user_badge import PreAuthenticatedUserBadge
from .passport.badge.user_badge import UserBadge
from .passport.self_validating_passport import SelfValidatingPassport

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_logging_contracts.context import Context
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from .passport.passport import Passport

__all__ = ["AbstractPreAuthenticatedAuthenticator"]


class AbstractPreAuthenticatedAuthenticator(
    AbstractAuthenticator,
    InteractiveAuthenticatorInterface,
):
    """The parts every pre-authenticated authenticator shares.

    A subclass reads the username its way — :meth:`extract_username`, the one
    abstract part — and everything else is decided here. A request whose
    reading yields no username is skipped, and so is one whose user already
    holds a pre-authenticated token for this firewall: the token from the
    session says everything a new one would. The passport states what makes
    this kind of authentication different — the user was authenticated
    before the passport was built, so it wears a
    :class:`~xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge.PreAuthenticatedUserBadge`
    and carries no credentials to check — and the token it settles on is a
    :class:`~xtr_security_core.authentication.token.pre_authenticated_token.PreAuthenticatedToken`.

    A failure clears the firewall's pre-authenticated token: whatever the
    token vouched for, the request that could not re-establish it invalidates
    it. And the login reports itself interactive — the user's own request
    established it, and the interactive-login announcement is how the rest of
    the flow learns that.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_firewall_name",
        "_logger",
        "_token_storage",
        "_user_provider",
    )

    def __init__(
        self,
        user_provider: UserProviderInterface,
        token_storage: TokenStorageInterface,
        firewall_name: str,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the provider, the storage, the firewall and the logger.

        Args:
            user_provider: Loads the user the request already names.
            token_storage: Read for a token that already vouches for the
                same user, and cleared when a failure invalidates one.
            firewall_name: The firewall this authenticator runs for; a token
                of another firewall is never its to clear.
            logger: Names what the authenticator skipped and cleared, when
                one is given.
        """
        self._user_provider: UserProviderInterface = user_provider
        self._token_storage: TokenStorageInterface = token_storage
        self._firewall_name: str = firewall_name
        self._logger: LoggerInterface | None = logger

    def extract_username(self, request: ServerRequestInterface) -> str | None:
        """Return the username the request already carries as proven.

        The one abstract part: each pre-authenticated authenticator reads the
        request its own way. ``None`` says the request carries no such user —
        the authenticator is skipped — and a
        :class:`~xtr_security_core.exception.BadCredentialsError` says the
        request claimed to carry one and turned out not to: also a skip, but
        one that clears any token the failure invalidates.
        """
        del request
        raise NotImplementedError(
            "A pre-authenticated authenticator must implement extract_username.",
        )

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle the request when it names a user this firewall has not settled yet.

        The reading is tried first: no user, or one the reading refuses,
        skips the authenticator — and a refusal clears the token it
        invalidates. A user who already holds a pre-authenticated token for
        this firewall skips it too: the token from the session vouches for
        everything a new one would. Anything else is this authenticator's
        request, and says why not when the tooling is listening.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        try:
            username = self.extract_username(request)
        except BadCredentialsError as error:
            self._clear_token(error)
            self._debug(
                "Skipping pre-authenticated authenticator as a bad-credentials error is raised.",
                {"authenticator": type(self).__name__},
            )
            _explain(reasons, str(error))
            return False
        if username is None:
            self._debug(
                "Skipping pre-authenticated authenticator: no username could be extracted.",
                {"authenticator": type(self).__name__},
            )
            _explain(reasons, "no user identifier was found in the request")
            return False
        token = self._token_storage.get_token()
        if (
            isinstance(token, PreAuthenticatedToken)
            and token.get_firewall_name() == self._firewall_name
            and token.get_user_identifier() == username
        ):
            self._debug(
                "Skipping pre-authenticated authenticator as the user already has an "
                "existing session.",
                {"authenticator": type(self).__name__},
            )
            _explain(
                reasons,
                f'the user "{username}" already has a pre-authenticated token for this firewall',
            )
            return False
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the username again, and build the passport around the provider.

        The reading runs here too, rather than being handed over from
        :meth:`supports`: a request message cannot be changed in place, and
        the pass that authenticates is handed the request as it arrived, not
        the one the supports pass read. The reading is the request's own
        environment, so reading it again answers what it answered before.

        Raises:
            BadCredentialsError: When the request no longer names a user —
                a caller that ran ``authenticate`` on a request the reading
                cannot even begin on.
        """
        username = self.extract_username(request)
        if username is None:
            raise BadCredentialsError(
                "No pre-authenticated user identifier was found in the request.",
            )
        return SelfValidatingPassport(
            UserBadge(username, user_loader=self._user_provider.load_user_by_identifier),
            [PreAuthenticatedUserBadge()],
        )

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a pre-authenticated token for the passport's user and roles.

        The user is read through the passport, which caches what the passport
        check already loaded, so this call does no I/O.
        """
        user = await passport.get_user()
        return PreAuthenticatedToken(user, firewall_name, user.get_roles())

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Clear the token the failure invalidates, and answer nothing.

        The request goes on anonymous — the access decision is what turns
        that into a challenge.
        """
        del request
        self._clear_token(error)
        return None

    @override
    def is_interactive(self) -> bool:
        """Report the login as the user's own act: their request established it."""
        return True

    def _clear_token(self, error: AuthenticationError) -> None:
        """Clear the firewall's pre-authenticated token, when the storage holds one.

        A token of another firewall is not this authenticator's to clear:
        the failure happened here, and only what this firewall settled is
        invalidated by it.
        """
        token = self._token_storage.get_token()
        if (
            isinstance(token, PreAuthenticatedToken)
            and token.get_firewall_name() == self._firewall_name
        ):
            self._token_storage.set_token(None)
            self._info(
                "Cleared pre-authenticated token due to an exception.",
                {"firewall": self._firewall_name, "error": type(error).__name__},
            )

    def _debug(self, message: str, context: Context) -> None:
        """Log ``message`` at debug level, when a logger was given."""
        if self._logger is not None:
            self._logger.debug(message, context)

    def _info(self, message: str, context: Context) -> None:
        """Log ``message`` at info level, when a logger was given."""
        if self._logger is not None:
            self._logger.info(message, context)


def _explain(reasons: object, why: str) -> None:
    """Record ``why`` this authenticator did not support the request, when asked."""
    if isinstance(reasons, UnsupportedReasons):
        reasons.add(why)
