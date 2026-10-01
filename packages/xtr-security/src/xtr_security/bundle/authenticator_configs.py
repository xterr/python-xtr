"""How a firewall proves a caller, described as inert data.

One authenticator ships here — the bearer access-token one — and the
authenticator-factory registry lets a later package add its own kind (seam S-1).
Each configuration is an instance a factory's ``config_type`` matches; the
firewall lists them under its ``authenticators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from .token_handler_configs import TokenHandlerConfig

__all__ = ["AccessTokenConfig"]

_KNOWN_EXTRACTORS = ("header", "query", "body")


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

    Raises:
        InvalidConfigurationError: When no extractor is named, or one is unknown.
    """

    token_handler: TokenHandlerConfig
    token_extractors: tuple[str, ...] = ("header",)
    realm: str | None = None

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
