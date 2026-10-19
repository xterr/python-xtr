"""The authenticator that turns a followed login link into a login."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http.exception import (
    InvalidLoginLinkAuthenticationError,
    InvalidLoginLinkErrorInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .fallback_user_loader import FallbackUserLoader
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .passport.badge.remember_me_badge import RememberMeBadge
from .passport.badge.user_badge import UserBadge
from .passport.self_validating_passport import SelfValidatingPassport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authentication.authentication_failure_handler_interface import (
        AuthenticationFailureHandlerInterface,
    )
    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )
    from xtr_security_http.http_utils import HttpUtils
    from xtr_security_http.login_link.login_link_handler_interface import (
        LoginLinkHandlerInterface,
    )

    from .passport.passport import Passport

__all__ = ["LoginLinkAuthenticator"]

#: Where a followed link arrives, and whether it must arrive by POST. The
#: ``check_path`` has no default: the wiring names the address a link leads to.
_DEFAULT_OPTIONS: dict[str, object] = {"check_path": None, "check_post_only": False}


@final
class LoginLinkAuthenticator(
    AbstractAuthenticator,
    InteractiveAuthenticatorInterface,
):
    """Authenticates the request that follows a login link.

    The link is followed at the configured check path — by a POST there,
    when the options demand one — and its ``user`` parameter names who the
    link was signed for. The link itself is the whole proof: the badge's
    loader spends it through the handler, so the passport validates
    itself around the user the spent link loads, wearing the remember-me
    badge a login this convenient is asked to outlive its session by.
    The answers are delegated: a success to the success handler, a
    failure to the failure handler.
    """

    __slots__ = (
        "_check_path",
        "_check_post_only",
        "_failure_handler",
        "_http_utils",
        "_login_link_handler",
        "_success_handler",
    )

    def __init__(
        self,
        login_link_handler: LoginLinkHandlerInterface,
        http_utils: HttpUtils,
        success_handler: AuthenticationSuccessHandlerInterface,
        failure_handler: AuthenticationFailureHandlerInterface,
        options: Mapping[str, object] | None = None,
    ) -> None:
        """Record the handler, the utils, the answer handlers and the options.

        Args:
            login_link_handler: Spends the link the request presents and
                loads the user it signs in.
            http_utils: Matches the check path.
            success_handler: Answers a successful login.
            failure_handler: Answers a failed one.
            options: The link's shape, merged over the defaults;
                ``check_path`` — where a followed link arrives — is
                required, the one option with no default to fall back on.

        Raises:
            InvalidArgumentError: When ``options`` carries no
                ``check_path``, or names where a link arrives by a route
                name.
        """
        self._login_link_handler = login_link_handler
        self._http_utils = http_utils
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        merged = {**_DEFAULT_OPTIONS, **(options or {})}
        if "check_route" in merged:
            raise InvalidArgumentError(
                'The "check_route" option is not supported: this stack has no routing '
                'component to resolve one by; configure the literal "check_path" a '
                "followed link arrives at.",
            )
        check_path = merged["check_path"]
        if not isinstance(check_path, str) or not check_path:
            raise InvalidArgumentError(
                "The login-link authenticator requires a check_path option naming "
                "where a followed link arrives.",
            )
        self._check_path = check_path
        self._check_post_only = bool(merged["check_post_only"])

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Handle the request that arrives at the check path.

        The method is weighed when the options demand a POST, and the
        path must be the configured check path; anything else says why
        when the tooling is listening.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if self._check_post_only and request.get_method() != "POST":
            _explain(
                reasons,
                f'the request method is "{request.get_method()}", and the '
                f'"check_post_only" option requires POST',
            )
            return False
        if not self._http_utils.check_request_path(request, self._check_path):
            _explain(
                reasons,
                f'the request path "{request.get_uri().get_path()}" does not match '
                f'the "check_path" option "{self._check_path}"',
            )
            return False
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the link's ``user`` parameter, and build the passport around spending it.

        The user is loaded by spending the link — the handler's check is
        the proof — so the badge's loader consumes it and hands back the
        user it signed in, wrapped as the badge's own loader so the
        wiring leaves it alone. The passport validates itself: there is
        no credential beyond the link, which the handler already checked.

        Raises:
            InvalidLoginLinkAuthenticationError: When the request carries
                no ``user`` parameter — a caller that ran ``authenticate``
                on a request the link's reading cannot even begin on.
        """
        username = query_parameter(request, "user")
        if username is None and request.get_method() not in ("GET", "HEAD"):
            username = payload_parameter(request, "user")
        if not isinstance(username, str) or not username:
            raise InvalidLoginLinkAuthenticationError("Missing user from link.")

        async def _spend(*arguments: object) -> UserInterface:
            # The badge names the user the link already named; the loader
            # is the link being spent, not a second opinion about the
            # identifier.
            del arguments
            try:
                return await self._login_link_handler.consume_login_link(request)
            except InvalidLoginLinkErrorInterface as error:
                raise InvalidLoginLinkAuthenticationError(
                    "Login link could not be validated.",
                ) from error

        return SelfValidatingPassport(
            UserBadge(username, user_loader=FallbackUserLoader(_spend)),
            [RememberMeBadge()],
        )

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Let the success handler answer."""
        del firewall_name
        return await self._success_handler.on_authentication_success(request, token)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Let the failure handler answer."""
        return await self._failure_handler.on_authentication_failure(request, error)

    @override
    def is_interactive(self) -> bool:
        """Report the login as the user's own act: they followed the link."""
        return True


def _explain(reasons: object, why: str) -> None:
    """Record ``why`` this authenticator did not support the request, when asked."""
    if isinstance(reasons, UnsupportedReasons):
        reasons.add(why)
