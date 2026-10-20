"""How a firewall proves a caller, described as inert data.

Two authenticators ship here — the bearer access-token one and the HTTP
basic one — and the authenticator-factory registry lets a later package add
its own kind (seam S-1). Each configuration is an instance a factory's
``config_type`` matches; the firewall lists them under its ``authenticators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from .token_handler_configs import TokenHandlerConfig

__all__ = ["AccessTokenConfig", "ExtractorName", "HttpBasicConfig"]

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
