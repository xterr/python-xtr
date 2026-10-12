"""Matches a redirect uri against the ones a client registered."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final
from urllib.parse import urlsplit, urlunsplit

from typing_extensions import override

from .redirect_uri_validator_interface import RedirectUriValidatorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from urllib.parse import SplitResult

__all__ = ["RedirectUriValidator"]

#: The two literals RFC 8252 section 7.3 names. The ``localhost`` name is not
#: among them on purpose: it resolves through the host file and may not be the
#: loopback at all, so a client registering it is held to its port like any
#: other host.
_LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "::1"})


def _readable_parts(url: str) -> SplitResult | None:
    """Split ``url`` into its parts, or report that it cannot be read.

    Reading the port is part of reading the uri: a port that is not a number
    makes the whole uri unreadable, and an unreadable uri gets no leniency —
    it only ever matches a registration that spells it the same way.
    """
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        return None
    return parts


def _is_loopback(url: str) -> bool:
    """Tell whether ``url`` is a loopback redirect as RFC 8252 section 7.3 defines one."""
    parts = _readable_parts(url)
    if parts is None:
        return False
    return parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS


def _without_port(url: str) -> str | None:
    """Return ``url`` with its port dropped, or ``None`` when it cannot be read.

    Only the port goes. Scheme, user information, host, path, query and
    fragment are rebuilt as they stand, so the leniency this buys a native
    client never widens into a second uri it may be answered at.
    """
    parts = _readable_parts(url)
    if parts is None:
        return None
    netloc = parts.netloc if parts.port is None else parts.netloc[: parts.netloc.rindex(":")]
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@final
class RedirectUriValidator(RedirectUriValidatorInterface):
    """Answers only at a uri the client registered, character for character.

    An exact comparison is the whole defence: a prefix or host comparison lets
    a client's own open redirect, or a path it does not control, carry an
    authorization code away. The single exception is the one RFC 8252 section
    7.3 grants a native client, which listens on whatever port the system hands
    it and cannot register that port in advance: a loopback redirect matches
    ignoring the port, and nothing else.
    """

    __slots__ = ("_allowed_redirect_uris",)

    def __init__(self, allowed_redirect_uris: Sequence[str] | str) -> None:
        """Hold the uris this client registered.

        Args:
            allowed_redirect_uris: Every registered uri, or the single one as a
                bare string — a client with one uri is the common case and
                upstream of this validator the value arrives either way.
        """
        self._allowed_redirect_uris: tuple[str, ...] = (
            (allowed_redirect_uris,)
            if isinstance(allowed_redirect_uris, str)
            else tuple(allowed_redirect_uris)
        )

    @override
    def validate_redirect_uri(self, redirect_uri: str) -> bool:
        """Tell whether ``redirect_uri`` is one of the registered ones."""
        if _is_loopback(redirect_uri):
            return self._matches_ignoring_the_port(redirect_uri)
        return redirect_uri in self._allowed_redirect_uris

    def _matches_ignoring_the_port(self, redirect_uri: str) -> bool:
        """Tell whether a registered uri equals ``redirect_uri`` but for its port."""
        candidate = _without_port(redirect_uri)
        if candidate is None:
            return False
        return any(_without_port(allowed) == candidate for allowed in self._allowed_redirect_uris)
