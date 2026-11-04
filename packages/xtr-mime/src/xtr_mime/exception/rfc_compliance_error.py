"""A value the mail standards do not allow."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError

__all__ = ["RfcComplianceError"]


class RfcComplianceError(InvalidArgumentError):
    """A value breaks the rules of the mail standards, so no server would accept it.

    An address that is not one, a domain that cannot be written in ASCII, a header parameter
    name that is not a token. A kind of :class:`InvalidArgumentError`, kept apart so a caller
    validating user input can tell "not an email address" from any other bad value.
    """
