"""Something was declared or configured in a way this library cannot work with."""

from __future__ import annotations

from .security_error import SecurityError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(SecurityError, ValueError):
    """A declaration, configuration or call was malformed.

    A decision asked for on several attributes at once, an attribute read from
    a token that carries none, a firewall referring to a provider that is not
    configured — mistakes caught where they are made. Also a
    :class:`ValueError`, so code guarding its configuration with
    ``except ValueError`` keeps working.
    """
