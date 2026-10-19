"""The parts of a remember-me handler every kind shares."""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .remember_me_cookie import RememberMeCookie
from .remember_me_handler_interface import RememberMeHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from .remember_me_details import RememberMeDetails

__all__ = ["AbstractRememberMeHandler"]

#: The options every handler carries, and their defaults. The name is the
#: cookie's own; the lifetime is one year, the longest a browser is asked to
#: keep a login that was never re-proven; the rest are the cookie's attributes,
#: repeated by the header that clears it. The last two belong to the listener
#: that decides whether a login wants the cookie at all — the handler carries
#: them so one options mapping serves the whole suite.
_DEFAULT_OPTIONS: Mapping[str, object] = {
    "name": "REMEMBERME",
    "lifetime": 31536000,
    "path": "/",
    "domain": None,
    "secure": False,
    "httponly": True,
    "samesite": None,
    "always_remember_me": False,
    "remember_me_parameter": "_remember_me",
}


class AbstractRememberMeHandler(  # pyright: ignore[reportImplicitAbstractClass]  -- subclasses implement process_remember_me
    RememberMeHandlerInterface,
):
    """Loads the user a cookie names, and stages the cookie every method sets.

    The two halves of a remember-me flow that no handler differs on: the
    user a cookie names is loaded through the user provider before the
    handler's own check runs, and the cookie — set or cleared — is staged on
    the request's security state, under the one key the response pass reads,
    because no response exists to put it on yet.

    A subclass implements :meth:`process_remember_me`: the check that the
    details still count, and the fresh cookie a consumed one must leave
    behind.
    """

    __slots__: tuple[str, ...] = ("_logger", "_options", "_user_provider")

    _user_provider: UserProviderInterface
    _logger: LoggerInterface | None
    _options: dict[str, object]

    def __init__(
        self,
        user_provider: UserProviderInterface,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the provider, the cookie's options and the logger.

        Args:
            user_provider: Loads the user a cookie names, before the
                handler's own check runs.
            options: The cookie's shape, merged over the defaults — ``name``,
                ``lifetime``, ``path``, ``domain``, ``secure``, ``httponly``,
                ``samesite``, and the two the conditions listener reads,
                ``always_remember_me`` and ``remember_me_parameter``.
            logger: Where the flow's decisions are logged, or ``None`` to
                log nowhere.
        """
        self._user_provider = user_provider
        self._options = {**_DEFAULT_OPTIONS, **(options or {})}
        self._logger = logger

    @override
    async def consume_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
    ) -> UserInterface:
        """Load the user the details name, then hand both to the check.

        The user is loaded before the check runs, because the check needs the
        user it is remembering — a signature is verified against the user's
        own fields, a stored token against what the user still is.

        Raises:
            AuthenticationError: When the provider knows no such user, or
                the handler's own check refuses the details.
        """
        user = await self._user_provider.load_user_by_identifier(
            remember_me_details.get_user_identifier(),
        )
        await self.process_remember_me(request, remember_me_details, user)
        self._info("Remember-me cookie accepted.")
        return user

    @override
    async def clear_remember_me_cookie(self, request: ServerRequestInterface) -> None:
        """Stage the clearing of the cookie, under the attributes it was set with."""
        self._debug("Clearing remember-me cookie.", {"name": self._options["name"]})
        self._create_cookie(request, None)

    @abstractmethod
    async def process_remember_me(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
        user: UserInterface,
    ) -> None:
        """Check the details against the user, and stage the fresh cookie.

        A consumed cookie is spent: the check runs here, and the fresh cookie
        the caller's next request will present is staged on the request —
        unless the handler's own policy keeps the current one, as a rotation
        window may.

        Raises:
            AuthenticationError: When the details do not check out against
                the user.
        """
        ...

    def _create_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails | None,
    ) -> None:
        """Stage the cookie for ``remember_me_details``, or its clearing.

        ``None`` clears: the request is answered with a header that drops the
        cookie, dated behind now on the path and domain it was set under. The
        staging fails loudly when the request carries no state bag — a caller
        running the flow without parking the kernel event's bag on the request
        it hands around.
        """
        options = self._options
        state = security_state_of(state_bag_of(request))
        state.attributes[SecurityRequestAttributes.REMEMBER_ME_COOKIE] = RememberMeCookie(
            name=str(options["name"]),
            value=None if remember_me_details is None else str(remember_me_details),
            expires=(
                None
                if remember_me_details is None
                else datetime.fromtimestamp(remember_me_details.get_expires(), UTC)
            ),
            path=_optional_str(options["path"]),
            domain=_optional_str(options["domain"]),
            secure=options["secure"] is True,
            httponly=options["httponly"] is not False,
            samesite=_optional_str(options["samesite"]),
        )

    def _lifetime(self) -> int:
        """Return the configured lifetime, as the seconds it names."""
        lifetime = self._options["lifetime"]
        return lifetime if isinstance(lifetime, int) else int(str(lifetime))

    def _debug(self, message: str, context: dict[str, object]) -> None:
        """Log ``message`` at debug level, when a logger was given."""
        if self._logger is not None:
            self._logger.debug(message, context)

    def _info(self, message: str) -> None:
        """Log ``message`` at info level, when a logger was given."""
        if self._logger is not None:
            self._logger.info(message, {})


def _optional_str(value: object) -> str | None:
    """Return ``value`` as the optional string a cookie attribute carries."""
    return value if isinstance(value, str) else None
