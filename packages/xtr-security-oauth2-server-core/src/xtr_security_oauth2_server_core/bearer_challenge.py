"""Writing the ``WWW-Authenticate`` challenge a caller that proved nothing is owed.

RFC 6750 section 3 has every challenge this server writes use the ``Bearer``
scheme, and that scheme "MUST be followed by one or more auth-param values" —
so a bare ``Bearer`` is not a challenge the standard admits. The section also
fixes which characters an auth-param value may carry: everything in
%x20-21 / %x23-5B / %x5D-7E, which is printable ASCII without the double quote
and the backslash. Anything outside that set is dropped rather than escaped,
because the set is what the section allows and a value that needed escaping
would already be outside it.

Two places answer a caller with a challenge — the entry point, which names the
realm, and the refusal of a presented token, which names the error code — so
the writing lives here once.
"""

from __future__ import annotations

from typing import Final

__all__ = ["bearer_challenge"]

#: The scheme every challenge here uses (RFC 6750, section 3).
_BEARER: Final[str] = "Bearer"

#: The characters an auth-param value may carry: %x20-21 / %x23-5B / %x5D-7E.
_ALLOWED: Final[frozenset[str]] = frozenset(
    {chr(point) for point in (*range(0x20, 0x22), *range(0x23, 0x5C), *range(0x5D, 0x7F))},
)


def bearer_challenge(name: str, value: str, **more: str) -> str:
    """Return the bearer challenge carrying these auth-params, in the order named.

    The first one is named on its own so that a challenge with none cannot be
    written at all: the scheme must be followed by one or more, and a caller
    with nothing to say has nothing to challenge with.

    Args:
        name: The first auth-param's name — ``realm``, or ``error``.
        value: Its value.
        more: Any further auth-param under its name. Each name is given once,
            which is what section 3 requires of ``realm``, ``scope``,
            ``error``, ``error_description`` and ``error_uri`` alike.

    Returns:
        The header value, each parameter written as a quoted string.
    """
    written = ", ".join(
        f'{param}="{_inside_the_set(given)}"' for param, given in ((name, value), *more.items())
    )

    return f"{_BEARER} {written}"


def _inside_the_set(value: str) -> str:
    """Return ``value`` with every character section 3 does not allow dropped."""
    return "".join(character for character in value if character in _ALLOWED)
