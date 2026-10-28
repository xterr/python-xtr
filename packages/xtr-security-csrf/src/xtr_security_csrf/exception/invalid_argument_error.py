"""Something was declared or configured in a way this library cannot work with."""

from __future__ import annotations

from .csrf_error import CsrfError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(CsrfError, ValueError):
    """A declaration, configuration or call was malformed.

    A generator asked for less entropy than a byte holds — mistakes caught
    where they are made. Also a :class:`ValueError`, so code guarding its
    configuration with ``except ValueError`` keeps working.
    """
