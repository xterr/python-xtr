"""Where a firewall reads a token from, as configuration.

The four extractor configurations a firewall may enable, grouped here as the
one thing they configure — where a token travels. The authorization header is
enabled by default; the others are opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "AuthorizationHeaderExtractorConfig",
    "CookieExtractorConfig",
    "QueryParameterExtractorConfig",
    "SplitCookieExtractorConfig",
    "TokenExtractorsConfig",
]


@dataclass(frozen=True, slots=True)
class AuthorizationHeaderExtractorConfig:
    """Read a token from a request header after a scheme prefix.

    Attributes:
        enabled: Whether the firewall reads a token from the header.
        prefix: The scheme word before the token, or empty for the whole value.
        name: The header the token travels in.
    """

    enabled: bool = True
    prefix: str = "Bearer"
    name: str = "Authorization"


@dataclass(frozen=True, slots=True)
class CookieExtractorConfig:
    """Read a token from a named cookie.

    Attributes:
        enabled: Whether the firewall reads a token from the cookie.
        name: The cookie the token travels in.
    """

    enabled: bool = False
    name: str = "BEARER"


@dataclass(frozen=True, slots=True)
class QueryParameterExtractorConfig:
    """Read a token from a named query parameter.

    Attributes:
        enabled: Whether the firewall reads a token from the query string.
        name: The query parameter the token travels in.
    """

    enabled: bool = False
    name: str = "bearer"


@dataclass(frozen=True, slots=True)
class SplitCookieExtractorConfig:
    """Read a token spread across several named cookies and rejoin it.

    Attributes:
        enabled: Whether the firewall reads a token split across cookies.
        cookies: The cookies the token is rebuilt from, in order.
    """

    enabled: bool = False
    cookies: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class TokenExtractorsConfig:
    """The four places a firewall may read a token from, grouped.

    Attributes:
        authorization_header: The header extractor, enabled by default.
        cookie: The cookie extractor, off by default.
        query_parameter: The query-parameter extractor, off by default.
        split_cookie: The split-cookie extractor, off by default.
    """

    authorization_header: AuthorizationHeaderExtractorConfig = field(
        default_factory=AuthorizationHeaderExtractorConfig,
    )
    cookie: CookieExtractorConfig = field(default_factory=CookieExtractorConfig)
    query_parameter: QueryParameterExtractorConfig = field(
        default_factory=QueryParameterExtractorConfig,
    )
    split_cookie: SplitCookieExtractorConfig = field(default_factory=SplitCookieExtractorConfig)

    def __post_init__(self) -> None:
        """Refuse a reading that enables no extractor at all.

        A firewall that could read a token from nowhere would accept none, so
        the misconfiguration fails where it is written — while the kernel builds
        the configuration — rather than at the first request that carries a token.

        Raises:
            InvalidArgumentError: When none of the four extractors is enabled.
        """
        enabled = (
            self.authorization_header.enabled,
            self.query_parameter.enabled,
            self.cookie.enabled,
            self.split_cookie.enabled,
        )
        if not any(enabled):
            raise InvalidArgumentError(
                "TokenExtractorsConfig enables no token extractor; a firewall must read "
                "a token from at least one of the authorization header, a cookie, a query "
                "parameter or split cookies.",
            )
