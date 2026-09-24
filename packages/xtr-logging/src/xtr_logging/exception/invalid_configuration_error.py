"""Configuration data does not describe a valid setup."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["InvalidConfigurationError"]


class InvalidConfigurationError(LoggingError):
    """Configuration data — parsed from a file or an environment — does not fit the schema.

    ``detail`` names what is wrong and where, as a JSON path: an unknown key,
    a value of the wrong type, a level that does not exist.
    """

    detail: str

    def __init__(self, detail: str) -> None:
        """Record what is wrong, and where."""
        self.detail = detail
        super().__init__(f"invalid logging configuration: {detail}")
