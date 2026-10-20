"""How a firewall proves a caller, described as inert data.

Four authenticators ship here — the bearer access-token one, the HTTP basic
one, the form login and the JSON login — and the authenticator-factory
registry lets a later package add its own kind (seam S-1). Each configuration
is an instance a factory's ``config_type`` matches; the firewall lists them
under its ``authenticators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from .token_handler_configs import TokenHandlerConfig

__all__ = [
    "AccessTokenConfig",
    "ExtractorName",
    "FormLoginConfig",
    "HttpBasicConfig",
    "JsonLoginConfig",
]

ExtractorName = Literal["header", "query", "body"]
"""The name of an extractor an access-token authenticator reads tokens by."""

_KNOWN_EXTRACTORS = get_args(ExtractorName)


@dataclass(frozen=True, slots=True)
class AccessTokenConfig:
    """A bearer access-token authenticator, built from a token handler.

    The handler validates the token and returns the user; the extractors read
    the token out of the request, tried in the order named — a chain of more
    than one, the first extractor's scheme documenting the firewall in OpenAPI.

    Attributes:
        token_handler: The token-handler configuration a factory builds.
        token_extractors: The extractors to read the token by, in order — any of
            ``"header"``, ``"query"``, ``"body"``.
        realm: The protection realm named in the ``WWW-Authenticate`` challenge.
        resource_metadata_uri: The URI the RFC 9728 ``resource_metadata``
            document lives at, absolutised against the request when it names a
            path; ``None`` omits the parameter from the challenge.
        sender_constraint: The qualifier of a registered
            :class:`~xtr_security_http.SenderConstraintInterface` service
            whose challenge the ``WWW-Authenticate`` parameters carry, or
            ``None`` for a plain bearer challenge.

    Raises:
        InvalidConfigurationError: When no extractor is named, or one is unknown.
    """

    token_handler: TokenHandlerConfig
    token_extractors: tuple[ExtractorName, ...] = ("header",)
    realm: str | None = None
    resource_metadata_uri: str | None = None
    sender_constraint: str | None = None

    def __post_init__(self) -> None:
        """Check every named extractor is one the bundle can build."""
        if not self.token_extractors:
            raise InvalidConfigurationError(
                "An access-token authenticator needs at least one token extractor.",
            )
        unknown = [name for name in self.token_extractors if name not in _KNOWN_EXTRACTORS]
        if unknown:
            raise InvalidConfigurationError(
                f"Unknown token extractor(s) {unknown}; known are {list(_KNOWN_EXTRACTORS)}.",
            )


@dataclass(frozen=True, slots=True)
class HttpBasicConfig:
    """An HTTP basic authenticator: the credentials the request itself carries.

    The browser's own ``Authorization: Basic`` header is the login form — no
    check path, no session — and its failed challenge is the entry point the
    browser answers with its credential prompt.

    Attributes:
        realm: The protection realm named in the ``WWW-Authenticate``
            challenge the browser labels its prompt with.

    Raises:
        InvalidConfigurationError: When no realm is given.
    """

    realm: str = "Secured"

    def __post_init__(self) -> None:
        """Check the realm is there to name the challenge."""
        if not self.realm:
            raise InvalidConfigurationError(
                "An HTTP basic authenticator needs a realm to name its challenge.",
            )


@dataclass(frozen=True, slots=True)
class FormLoginConfig:
    """A form login: the page a form lives on, and the submission that proves it.

    The form is rendered at ``login_path`` and submitted to ``check_path`` — a
    POST there, its fields read by the names the form gives them. A form
    carries a session — the page it renders stores its errors in one, the
    login it lands in rotates it — so it belongs on a stateful firewall only.

    Attributes:
        login_path: The path of the page the form lives on; the entry point
            redirects an unauthenticated request to it.
        check_path: The path the form is submitted to.
        username_parameter: The field the form carries the username under.
        password_parameter: The field the form carries the password under.
        post_only: Whether only a POST to the check path is the form's
            submission.
        form_only: Whether the submission must also carry a form content type.
        enable_csrf: Whether the form carries a cross-site request forgery
            token, checked against the session's stored one.
        csrf_parameter: The field the form carries the forgery token under.
        csrf_token_id: The id the forgery token is stored under.
        success_handler: The application's own success-handler service type,
            answered through the bundle's wrapper — or ``None`` for the
            default redirect by the target ladder.
        failure_handler: The application's own failure-handler service type,
            answered through the bundle's wrapper — or ``None`` for the
            default redirect to the login page, the error stored on the
            session.

    Raises:
        InvalidConfigurationError: When the login path is empty.
    """

    login_path: str
    check_path: str = "/login_check"
    username_parameter: str = "_username"
    password_parameter: str = "_password"  # noqa: S105 -- the field's name, not a credential
    post_only: bool = True
    form_only: bool = False
    enable_csrf: bool = False
    csrf_parameter: str = "_csrf_token"
    csrf_token_id: str = "authenticate"  # noqa: S105 -- the token's id, not a credential
    success_handler: type | None = None
    failure_handler: type | None = None

    def __post_init__(self) -> None:
        """Check the page the form lives on is named."""
        if not self.login_path:
            raise InvalidConfigurationError(
                "A form login needs the path of the page its form lives on.",
            )


@dataclass(frozen=True, slots=True)
class JsonLoginConfig:
    """A JSON login: a document carrying a username and a password.

    The document is the request's parsed body — its two members read by the
    dotted paths the configuration names — and the login is stateless: the
    request that carries the document is itself the proof, answered with a
    plain ``401`` when it fails and no handler is configured.

    Attributes:
        check_path: The path the document is submitted to, or ``None`` for
            every request carrying a JSON body.
        username_path: The dotted path of the member carrying the username.
        password_path: The dotted path of the member carrying the password.
        success_handler: The application's own success-handler service type,
            or ``None`` to let the request reach its endpoint with the token
            now set.
        failure_handler: The application's own failure-handler service type,
            or ``None`` to answer a failed login with a ``401`` carrying the
            error's message.

    Raises:
        InvalidConfigurationError: When the check path is empty rather than
            absent.
    """

    check_path: str | None = None
    username_path: str = "username"
    password_path: str = "password"  # noqa: S105 -- the member's name, not a credential
    success_handler: type | None = None
    failure_handler: type | None = None

    def __post_init__(self) -> None:
        """Refuse a check path that names nothing."""
        if self.check_path == "":
            raise InvalidConfigurationError(
                'A JSON login names the check path "" — set the path the document '
                "is submitted to, or None for every request carrying one.",
            )
