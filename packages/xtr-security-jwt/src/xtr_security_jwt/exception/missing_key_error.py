"""The configuration error raised when the key a token needs is not there."""

from __future__ import annotations

from typing import final

from xtr_security_core.exception import InvalidArgumentError

__all__ = ["MissingKeyError"]

_HINT = (
    "set secret_key in <app>/config/jwt.py — usually a path read from JWT_SECRET_KEY_PATH — "
    "or mint one with jwt:generate-keypair --output-dir secrets"
)


@final
class MissingKeyError(InvalidArgumentError):
    """No signing or verifying key is configured, or the key file it names is not there.

    The bundle builds and boots without a key, so the console stays usable to
    mint one; the absence is reported here, the first time a token is signed or
    verified. It is a deployment's mistake, never a client's: the encoder lets it
    through rather than reporting it as a token that failed to verify, so a
    request meeting it fails as a server error instead of a ``401``.

    Attributes:
        location: The key file that was looked for, or ``None`` when no key is
            configured at all.
    """

    location: str | None

    def __init__(self, location: str | None = None) -> None:
        """Record the key file looked for, or that no key is configured at all."""
        self.location = location
        found = (
            "No JWT key is configured"
            if location is None
            else f"The key file {location!r} does not exist"
        )
        super().__init__(f"{found}: {_HINT}.")
