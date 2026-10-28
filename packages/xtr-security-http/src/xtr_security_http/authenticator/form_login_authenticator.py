"""The form-login authenticator: a username and a password read out of a submitted form."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import BadCredentialsError, InvalidArgumentError
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http.entry_point.re_authentication_entry_point_interface import (
    ReAuthenticationEntryPointInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._form_login_credentials import form_login_credentials_of
from .abstract_login_form_authenticator import AbstractLoginFormAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .passport.badge.authentication_method_badge import AuthenticationMethodBadge
from .passport.badge.csrf_token_badge import CsrfTokenBadge
from .passport.badge.password_upgrade_badge import PasswordUpgradeBadge
from .passport.badge.remember_me_badge import RememberMeBadge
from .passport.badge.user_badge import UserBadge
from .passport.credentials.password_credentials import PasswordCredentials
from .passport.passport import Passport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.authentication.authentication_failure_handler_interface import (
        AuthenticationFailureHandlerInterface,
    )
    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )
    from xtr_security_http.http_utils import HttpUtils

__all__ = ["FormLoginAuthenticator"]

#: The form's field names and paths, and their defaults. The ``login_path``
#: has no default: the wiring names the page the form lives on.
_DEFAULT_OPTIONS: dict[str, object] = {
    "username_parameter": "_username",
    "password_parameter": "_password",
    "check_path": "/login_check",
    "post_only": True,
    "form_only": False,
    "enable_csrf": False,
    "csrf_parameter": "_csrf_token",
    "csrf_token_id": "authenticate",
}


@final
class FormLoginAuthenticator(
    AbstractLoginFormAuthenticator,
    ReAuthenticationEntryPointInterface,
):
    """Authenticates a form's submission: a username and a password.

    The form is submitted to the configured check path — a POST there, a
    form content type when the options demand one — and its fields are read
    by the configured names. The username is kept on the session for the
    form that renders again, the passport carries a password credential
    with badges for the method, the remember-me conditions and — when the
    options enable it — the cross-site request forgery token the form
    presented, and the token the login earns is a username-password one.

    The answers are delegated: a success to the success handler, a failure
    to the failure handler. A re-authentication — a caller already
    authenticated, asked to prove themselves again — ends with the login
    form, the caller's identifier kept on the session for it.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_failure_handler",
        "_options",
        "_success_handler",
        "_user_provider",
    )

    def __init__(
        self,
        http_utils: HttpUtils,
        user_provider: UserProviderInterface,
        success_handler: AuthenticationSuccessHandlerInterface,
        failure_handler: AuthenticationFailureHandlerInterface,
        options: Mapping[str, object] | None = None,
    ) -> None:
        """Record the form's shape and the handlers that answer its login.

        Args:
            http_utils: Matches the check path and builds the redirects.
            user_provider: Loads the user the form's username names.
            success_handler: Answers a successful login.
            failure_handler: Answers a failed one.
            options: The form's field names and paths, merged over the
                defaults; ``login_path`` — the page the form lives on — is
                required, the one option with no default to fall back on.

        Raises:
            InvalidArgumentError: When ``options`` carries no ``login_path``
                — the wiring must name the page the form lives on.
        """
        super().__init__(http_utils)
        self._user_provider = user_provider
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        self._options = {**_DEFAULT_OPTIONS, **(options or {})}
        login_path = self._options.get("login_path")
        if not isinstance(login_path, str) or not login_path:
            raise InvalidArgumentError(
                "The form-login authenticator requires a login_path option naming the page "
                "the form lives on.",
            )

    @override
    def get_login_url(self, request: ServerRequestInterface) -> str:
        """Return the URI of the page the form lives on."""
        del request
        return self._http_utils.generate_uri(str(self._options["login_path"]))

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle the request only when it is this form's submission.

        The method is weighed when the options demand a POST, the path must
        be the configured check path, and the content type a form's when
        the options demand one; anything else says why when the tooling is
        listening.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if self._options["post_only"] and request.get_method() != "POST":
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the request method is "{request.get_method()}", '
                    f'and the "post_only" option requires POST',
                )
            return False
        check_path = str(self._options["check_path"])
        if not self._http_utils.check_request_path(request, check_path):
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the request path "{request.get_uri().get_path()}" does not match '
                    f'the "check_path" option "{check_path}"',
                )
            return False
        if self._options["form_only"] and not _is_form_content_type(
            request.get_header_line("Content-Type"),
        ):
            content_type = request.get_header_line("Content-Type")
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the "Content-Type" header is "{content_type}", '
                    f'and the "form_only" option requires a form one',
                )
            return False
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the form's submission into a passport.

        The username is trimmed and kept on the session for the form that
        renders again; the password is read but never kept anywhere but the
        credential that verifies it. A field that is missing, empty or not a
        string at all fails the login as a bad credential — the form is
        answered, not the request rejected.
        """
        username, password, csrf_token = form_login_credentials_of(request, self._options)
        session = parked_session_of(request)
        if session is None:
            raise BadCredentialsError(
                "The form login has no session to keep its username on: a stateful "
                "firewall must run for the request.",
            )
        await session.set(SecurityRequestAttributes.LAST_USERNAME, username)
        passport = Passport(
            UserBadge(username, user_loader=self._user_provider.load_user_by_identifier),
            PasswordCredentials(password),
            [RememberMeBadge(), AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)],
        )
        if self._options["enable_csrf"]:
            _ = passport.add_badge(
                CsrfTokenBadge(
                    str(self._options["csrf_token_id"]),
                    csrf_token if isinstance(csrf_token, str) else None,
                ),
            )
        if isinstance(self._user_provider, PasswordUpgraderInterface):
            _ = passport.add_badge(PasswordUpgradeBadge(password, self._user_provider))
        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a username-password token for the user the form's submission proved."""
        user = await passport.get_user()
        return UsernamePasswordToken(user, firewall_name, user.get_roles())

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """End any re-authentication this login answered, then let the handler answer.

        Whether or not a login page read the attribute, the
        re-authentication is over: the caller proved themselves, so the
        attribute that named what they were being asked for is removed.
        """
        del firewall_name
        session = parked_session_of(request)
        if session is not None:
            _ = await session.remove(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE)
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
    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        """Send the caller to the login form to type their password again.

        Their identifier and the attribute they were denied for are kept on
        the session for the login page, so the form re-fills the identifier
        and the page knows what it is asking for. They land back on the
        resource they were denied as long as the success handler uses the
        target path saved before this — which ``always_use_default_target_path``
        and a ``_target_path`` of the form both outrank.
        """
        session = parked_session_of(request)
        if session is not None:
            await session.set(SecurityRequestAttributes.LAST_USERNAME, token.get_user_identifier())
            await session.set(
                SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE,
                request.get_attribute(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE),
            )
        return await self.start(request)


def _is_form_content_type(content_type: str) -> bool:
    """Tell whether a ``Content-Type`` header names one of the form encodings."""
    media = content_type.partition(";")[0].strip().lower()
    return media.startswith(("application/x-www-form-urlencoded", "multipart/form-data"))
