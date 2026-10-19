"""The HTTP basic authenticator: a challenge answered by the same challenge.

A request that carries basic credentials is authenticated by them — a
username and a password read off the ``Authorization`` header — and a
request that reaches a protected page without any is answered by the
``401`` that asks for them, the ``WWW-Authenticate`` header naming the
realm. A failed attempt is answered the same way: the caller is invited to
try again, not turned away.
"""

from __future__ import annotations

from base64 import b64decode
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from xtr_security_http._challenge import no_store_headers
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .passport.badge.authentication_method_badge import AuthenticationMethodBadge
from .passport.badge.password_upgrade_badge import PasswordUpgradeBadge
from .passport.badge.user_badge import UserBadge
from .passport.credentials.password_credentials import PasswordCredentials
from .passport.passport import Passport

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_http_message_contracts.factory import ResponseFactoryInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["HttpBasicAuthenticator"]


@final
class HttpBasicAuthenticator(AbstractAuthenticator, AuthenticationEntryPointInterface):
    """Authenticates the basic credentials a request's ``Authorization`` header carries.

    The header's ``Basic`` scheme carries the username and the password
    base64-encoded — the colon inside them splits the two, and a password
    may itself carry colons. The passport carries a password credential
    with a badge for the method, and the token the login earns is a
    username-password one.
    """

    __slots__ = ("_logger", "_realm_name", "_responses", "_user_provider")

    def __init__(
        self,
        realm_name: str,
        user_provider: UserProviderInterface,
        responses: ResponseFactoryInterface,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the realm, the provider, the response factory and the logger.

        Args:
            realm_name: The protection realm named in the challenge, so the
                caller's agent can label the prompt it shows.
            user_provider: Loads the user the credentials' username names.
            responses: Builds the challenge responses, so the class names
                no response class.
            logger: Logs a failed attempt, when one is given.
        """
        self._realm_name = realm_name
        self._user_provider = user_provider
        self._responses = responses
        self._logger = logger

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Answer with the ``401`` that asks for basic credentials.

        The challenge names the realm, and carries the no-store directives
        every challenge this package writes does, so a shared cache never
        keeps a ``401`` and replays it to another caller.
        """
        del request, error
        response = self._responses.create_response(401)
        for name, value in no_store_headers(
            **{"WWW-Authenticate": f'Basic realm="{self._realm_name}"'},
        ).items():
            response = response.with_header(name.lower(), value)
        return response

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle the request only when it carries basic credentials.

        A request without them is not failed — it simply has nothing for
        this authenticator to read, and says so when the tooling is
        listening.
        """
        if not _authorization_of(request).startswith("Basic "):
            reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    'the request carries no HTTP basic credentials, as no "Authorization: Basic" '
                    "header is set",
                )
            return False
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the header's credentials into a passport."""
        username, password = _credentials_of(request)
        passport = Passport(
            UserBadge(username, user_loader=self._user_provider.load_user_by_identifier),
            PasswordCredentials(password),
            [AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)],
        )
        if isinstance(self._user_provider, PasswordUpgraderInterface):
            _ = passport.add_badge(PasswordUpgradeBadge(password, self._user_provider))
        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a username-password token for the user the credentials proved."""
        user = await passport.get_user()
        return UsernamePasswordToken(user, firewall_name, user.get_roles())

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Log the failed attempt, then answer with the challenge again."""
        if self._logger is not None:
            self._logger.info(
                "Basic authentication failed for user.",
                {"username": _credentials_of(request)[0], "error": error},
            )
        return await self.start(request, error)


def _authorization_of(request: ServerRequestInterface) -> str:
    """Return the request's ``Authorization`` header, case-corrected for the scheme."""
    header = request.get_header_line("Authorization")
    scheme, separator, rest = header.partition(" ")
    if separator and scheme.lower() == "basic":
        return f"Basic {rest}"
    return header


def _credentials_of(request: ServerRequestInterface) -> tuple[str, str]:
    """Return the username and the password the ``Authorization`` header carries.

    The header's payload is base64-encoded text with the username before
    the first colon and the password after it — colons and all.

    Raises:
        BadCredentialsError: When the header's payload does not decode, or
            names no username.
    """
    encoded = _authorization_of(request).partition(" ")[2]
    try:
        decoded = b64decode(encoded, validate=True).decode("utf-8")
    except ValueError as error:
        raise BadCredentialsError(
            "The HTTP basic credentials are not correctly encoded.",
        ) from error
    username, _, password = decoded.partition(":")
    if username == "":
        raise BadCredentialsError("The HTTP basic credentials name no username.")
    return username, password
