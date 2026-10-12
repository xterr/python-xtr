"""What the resource-server side reads an access token against."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

__all__ = ["ResourceServerConfig"]


@dataclass(frozen=True, slots=True)
class ResourceServerConfig:
    """How an API reading this server's tokens verifies them.

    Both settings are optional, and the common deployment sets neither: one
    process issues the tokens and reads them, so the verifying key is the
    public half of the signing key and there is no clock to disagree with.

    Attributes:
        public_key: The key access tokens are verified against, as PEM text or
            the path of a file holding it, or ``None`` to derive it from the
            signing key. A resource server running apart from the authorization
            server is the case for setting it: it holds the public half and
            never the private one.
        jwt_leeway: How far the expiry and not-before windows are widened for
            clocks that disagree, or ``None`` for not at all. Every second of
            leeway is a second a withdrawn-by-expiry token keeps working, so
            the default is none.
    """

    public_key: str | None = None
    jwt_leeway: timedelta | None = None

    def __post_init__(self) -> None:
        """Refuse a negative leeway.

        Raises:
            InvalidConfigurationError: When the leeway is negative, which would
                narrow a token's validity instead of widening it — the opposite
                of what the setting is for.
        """
        if self.jwt_leeway is not None and self.jwt_leeway < timedelta(0):
            raise InvalidConfigurationError(
                f"The setting resource_server.jwt_leeway is {self.jwt_leeway}; leeway widens "
                "the window a token is accepted in, so it cannot be negative.",
            )
