"""A stateless login over a JSON document of a username and a password."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeGuard, final
from urllib.parse import unquote

from typing_extensions import override
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from xtr_security_http._challenge import json_challenge
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .passport.badge.authentication_method_badge import AuthenticationMethodBadge
from .passport.badge.password_upgrade_badge import PasswordUpgradeBadge
from .passport.badge.remember_me_badge import RememberMeBadge
from .passport.badge.user_badge import UserBadge
from .passport.credentials.password_credentials import PasswordCredentials
from .passport.passport import Passport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_http_message_contracts.factory import ResponseFactoryInterface
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

__all__ = ["JsonLoginAuthenticator"]

#: Where the username and the password live in the JSON document, and their
#: defaults.
_DEFAULT_OPTIONS: dict[str, object] = {
    "username_path": "username",
    "password_path": "password",
}


@final
class JsonLoginAuthenticator(AbstractAuthenticator, InteractiveAuthenticatorInterface):
    """Authenticates a JSON document: a username and a password, statelessly.

    The document is the request's parsed body — a JSON object, its two
    fields read by the configured paths — and the login answers as a
    machine reads it: no redirect to a form, a ``401`` carrying the error's
    message when no failure handler is given. The passport carries a
    password credential with badges for the method and the remember-me
    conditions — the document's own fields, the password erased from them
    first — and the token the login earns is a username-password one.
    """

    __slots__ = (
        "_failure_handler",
        "_http_utils",
        "_options",
        "_responses",
        "_success_handler",
        "_user_provider",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the translated constructor; every parameter is upstream's
        self,
        http_utils: HttpUtils,
        user_provider: UserProviderInterface,
        responses: ResponseFactoryInterface,
        success_handler: AuthenticationSuccessHandlerInterface | None = None,
        failure_handler: AuthenticationFailureHandlerInterface | None = None,
        options: Mapping[str, object] | None = None,
    ) -> None:
        """Record the document's shape and the handlers that answer its login.

        Args:
            http_utils: Matches the check path, when one is configured.
            user_provider: Loads the user the document's username names.
            responses: Builds the ``401`` a failure without a handler
                answers with, so the class names no response class.
            success_handler: Answers a successful login, or ``None`` to let
                the request reach its endpoint with the token now set.
            failure_handler: Answers a failed one, or ``None`` to answer
                with a ``401`` carrying the error's message.
            options: Where the username and the password live in the
                document, merged over the defaults.
        """
        self._http_utils = http_utils
        self._user_provider = user_provider
        self._responses = responses
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        self._options = {**_DEFAULT_OPTIONS, **(options or {})}

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle the request only when its body is a JSON document.

        The content type names the JSON body; the path must be the
        configured check path, when one is configured. Anything else says
        why when the tooling is listening.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        content_type = request.get_header_line("Content-Type")
        if "json" not in content_type:
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the "Content-Type" header "{content_type}" is not a JSON one'
                    if content_type != ""
                    else 'the request has no "Content-Type" header, and none is a JSON one',
                )
            return False
        check_path = self._options.get("check_path")
        if isinstance(check_path, str) and not self._http_utils.check_request_path(
            request,
            check_path,
        ):
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the request path "{unquote(request.get_uri().get_path())}" does not match '
                    f'the "check_path" option "{check_path}"',
                )
            return False
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read the document into a passport.

        The two fields are read by their configured paths — a dotted path
        walks into a nested document — and the password is erased from the
        document before any of it rides along as remember-me parameters:
        the conditions a listener reads are the document's own fields, never
        the password. A field that is missing, empty or not a string at all
        fails the login as a bad credential.
        """
        document = request.get_parsed_body()
        if not _is_json_object(document):
            raise BadCredentialsError("Invalid JSON.")
        username_path = str(self._options["username_path"])
        password_path = str(self._options["password_path"])
        username = _value_at(document, username_path)
        if not isinstance(username, str):
            raise BadCredentialsError(f'The key "{username_path}" must be a string.')
        if username == "":
            raise BadCredentialsError(f'The key "{username_path}" must not be empty.')
        password = _value_at(document, password_path)
        if not isinstance(password, str):
            raise BadCredentialsError(f'The key "{password_path}" must be a string.')
        if password == "":
            raise BadCredentialsError(f'The key "{password_path}" must not be empty.')
        _erase_at(document, password_path)
        passport = Passport(
            UserBadge(username, user_loader=self._user_provider.load_user_by_identifier),
            PasswordCredentials(password),
            [
                RememberMeBadge(dict(document)),
                AuthenticationMethodBadge(AuthenticationMethod.PASSWORD),
            ],
        )
        if isinstance(self._user_provider, PasswordUpgraderInterface):
            _ = passport.add_badge(PasswordUpgradeBadge(password, self._user_provider))
        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a username-password token for the user the document proved."""
        user = await passport.get_user()
        return UsernamePasswordToken(user, firewall_name, user.get_roles())

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Let the handler answer, or the request reach its endpoint."""
        del firewall_name
        if self._success_handler is None:
            return None
        return await self._success_handler.on_authentication_success(request, token)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Let the handler answer, or answer with a ``401`` carrying the error's message."""
        if self._failure_handler is not None:
            return await self._failure_handler.on_authentication_failure(request, error)
        return await json_challenge(self._responses, 401, {"error": str(error)}, {})

    @override
    def is_interactive(self) -> bool:
        """Announce the login as the user's own act: a document is submitted by hand."""
        return True


def _value_at(document: dict[str, object], path: str) -> object:
    """Return the value a dotted ``path`` names in ``document``.

    Each step of the path walks one object deeper, so ``user.name`` reads
    the ``name`` field of the ``user`` field. A step that is not there is
    the field missing, and says so.

    Raises:
        BadCredentialsError: When a step of ``path`` names no field — the
            document the caller submitted has no such field.
    """
    value: object = document
    for step in path.split("."):
        if not _is_json_object(value) or step not in value:
            raise BadCredentialsError(f'The key "{path}" must be provided.')
        value = value[step]
    return value


def _erase_at(document: dict[str, object], path: str) -> None:
    """Set the value a dotted ``path`` names in ``document`` to ``None``.

    The document's own fields may ride along as remember-me parameters;
    the password is not one of them, so it is erased before they do.
    """
    steps = path.split(".")
    value: object = document
    for step in steps[:-1]:
        if not _is_json_object(value):
            return
        value = value[step]
    if _is_json_object(value):
        value[steps[-1]] = None


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Tell whether ``value`` is a JSON object: a mapping keyed by strings.

    The JSON grammar keys an object with strings and nothing else, so a
    value that parses from a JSON object at all is keyed the one way a
    path can walk it.
    """
    return isinstance(value, dict)
