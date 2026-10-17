"""Why an authenticator did not support a request, in the wrapper's own words."""

from __future__ import annotations

from typing import final

__all__ = ["UnsupportedReasons"]


@final
class UnsupportedReasons:
    """Collects the reasons an authenticator declined to support a request.

    A traceable wrapper parks one of these on the request — under
    :attr:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes.UNSUPPORTED_REASONS`
    — for the duration of the wrapped authenticator's ``supports`` call, so
    the authenticator can explain a negative answer while it gives it:

    .. code-block:: python

        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if isinstance(reasons, UnsupportedReasons):
            reasons.add("the request carries no bearer token")

    The attribute is absent otherwise, so explaining costs nothing when
    nobody is listening.
    """

    __slots__ = ("_reasons",)

    def __init__(self) -> None:
        """Start with no reasons collected."""
        self._reasons: list[str] = []

    def add(self, reason: str) -> None:
        """Collect ``reason`` as one more explanation of a negative answer."""
        self._reasons.append(reason)

    def all(self) -> tuple[str, ...]:
        """Return every reason collected, in the order they were added."""
        return tuple(self._reasons)
