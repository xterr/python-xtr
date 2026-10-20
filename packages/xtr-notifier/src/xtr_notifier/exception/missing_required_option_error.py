"""A DSN without an option its transport requires."""

from __future__ import annotations

from .incomplete_dsn_error import IncompleteDsnError

__all__ = ["MissingRequiredOptionError"]


class MissingRequiredOptionError(IncompleteDsnError):
    """A DSN leaves out, or leaves blank, a query option its transport requires.

    Attributes:
        option: The option that is missing.
    """

    option: str

    def __init__(self, option: str, dsn: str | None = None) -> None:
        """Name the missing option.

        Args:
            option: The option that is missing.
            dsn: The DSN it is missing from, without credentials, when known.
        """
        self.option = option
        super().__init__(f'The option "{option}" is required but missing.', dsn)
