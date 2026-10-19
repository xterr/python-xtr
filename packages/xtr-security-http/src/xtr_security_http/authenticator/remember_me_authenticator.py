"""The authenticator that turns a returning remember-me cookie into a login."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    TokenStorageInterface,
)
from xtr_security_core.exception import (
    BadMethodCallError,
    CookieTheftError,
    UserNotFoundError,
)

from xtr_security_http._security_state import security_state_of
from xtr_security_http.remember_me.remember_me_cookie import RememberMeCookie
from xtr_security_http.remember_me.remember_me_details import RememberMeDetails
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .passport.badge.user_badge import UserBadge
from .passport.self_validating_passport import SelfValidatingPassport

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.remember_me.remember_me_handler_interface import (
        RememberMeHandlerInterface,
    )

    from .passport.passport import Passport

__all__ = ["RememberMeAuthenticator"]


@final
class RememberMeAuthenticator(
    AbstractAuthenticator,
    InteractiveAuthenticatorInterface,
):
    """Re-establishes the user a remember-me cookie remembers.

    Runs when the request carries the cookie and nothing else already has —
    a session that expired, a login the cookie outlived. The cookie is read
    into its details and spent through the handler: the handler's check is
    the whole proof, so the passport validates itself around the user the
    spent cookie loads, and the token the login settles on is a remembered
    one — authenticated, but a trust resolver tells it apart from a fully
    proven login.

    Presenting a cookie is no explicit act of the user's, yet the login it
    re-establishes has been announced as an interactive one for as long as
    the flow has existed, and the listeners that react to a user coming
    back — one updating a last-login date — rely on the announcement; so
    this authenticator reports itself interactive, as it always has.
    """

    __slots__ = ("_cookie_name", "_logger", "_remember_me_handler", "_token_storage")

    def __init__(
        self,
        remember_me_handler: RememberMeHandlerInterface,
        token_storage: TokenStorageInterface,
        cookie_name: str,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the handler, the storage, the cookie's name and the logger.

        Args:
            remember_me_handler: Spends the cookie the request presented and
                loads the user it remembers.
            token_storage: Holds the request's token, read to keep this
                authenticator from overwriting one a session already
                stored.
            cookie_name: The name the cookie travels under.
            logger: Where the flow's decisions are logged, or ``None``.
        """
        self._remember_me_handler = remember_me_handler
        self._token_storage = token_storage
        self._cookie_name = cookie_name
        self._logger = logger

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer whether the request presents a cookie worth spending.

        A request whose storage already holds a token is authenticated —
        the cookie must not overwrite it. One whose state staged the
        cookie's clearing — a logout in flight — must not spend what the
        same request is dropping. A request with no cookie, or an empty
        one, has nothing to spend. Anything else presents a cookie this
        authenticator handles lazily: ``None``, so a later authenticator
        may still run when this one yields no token.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if self._token_storage.get_token() is not None:
            _explain(reasons, "a token is already stored, so the request is already authenticated")
            return False
        staged = _staged_cookie_of(request)
        if staged is not None and staged.value is None:
            _explain(reasons, f'the "{self._cookie_name}" cookie is being cleared by this request')
            return False
        cookies = request.get_cookie_params()
        if self._cookie_name not in cookies:
            _explain(reasons, f'the request has no "{self._cookie_name}" cookie')
            return False
        if cookies[self._cookie_name] == "":
            _explain(reasons, f'the "{self._cookie_name}" cookie is empty or not a scalar')
            return False
        if self._logger is not None:
            self._logger.debug("Remember-me cookie detected.", {})
        return None

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the cookie into details, and build the passport around spending it.

        The user is loaded by spending the cookie — the handler's check is
        the proof — so the badge's loader consumes it and hands back the
        user it remembered. The passport validates itself: there is no
        credential beyond the cookie, which the handler already checked.

        Raises:
            BadMethodCallError: When the request carries no cookie — a
                caller that ran ``authenticate`` without ``supports``
                having found one.
            AuthenticationError: When the cookie does not read into the
                details a handler wrote, or the handler refuses to spend
                it.
        """
        raw = request.get_cookie_params().get(self._cookie_name)
        if not raw:
            raise BadMethodCallError("No remember-me cookie is found.")
        details = RememberMeDetails.from_raw_cookie(raw)

        async def _spend(identifier: str) -> UserInterface:
            # The badge names the user the cookie already named; the loader
            # is the cookie being spent, not a second opinion about the
            # identifier.
            del identifier
            return await self._remember_me_handler.consume_remember_me_cookie(request, details)

        return SelfValidatingPassport(UserBadge(details.get_user_identifier(), user_loader=_spend))

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a remembered token for the user the spent cookie loaded."""
        user = await passport.get_user()
        return RememberMeToken(user, firewall_name)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Log the failure by what it says about the cookie, and answer nothing.

        A theft is not logged here — the handler already raised it loudly,
        and the error's own reporting is the record that matters. The
        request goes on anonymous: the access decision is what turns that
        into the entry point's challenge.
        """
        del request
        if self._logger is not None:
            if isinstance(error, UserNotFoundError):
                self._logger.info("User for remember-me cookie not found.", {"exception": error})
            elif not isinstance(error, CookieTheftError):
                self._logger.debug("Remember me authentication failed.", {"exception": error})
        return None

    @override
    def is_interactive(self) -> bool:
        """Report the login as the user's own act, as the flow always has."""
        return True


def _staged_cookie_of(request: ServerRequestInterface) -> RememberMeCookie | None:
    """Return the remember-me cookie staged on the request's state, if one is.

    The supports pass must not raise over a lookup: a request whose caller
    parked no state bag is one this authenticator does not run for, and
    reading the staged cookie off it answers the same as finding none.
    """
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    if not isinstance(bag, MutableMapping):
        return None
    # The cast says what narrowing cannot: a mapping of anything is a mapping
    # of objects, the shape the carrier reads.
    staged = security_state_of(cast("MutableMapping[str, object]", bag)).attributes.get(
        SecurityRequestAttributes.REMEMBER_ME_COOKIE,
    )
    return staged if isinstance(staged, RememberMeCookie) else None


def _explain(reasons: object, why: str) -> None:
    """Record ``why`` this authenticator did not support the request, when asked."""
    if isinstance(reasons, UnsupportedReasons):
        reasons.add(why)
