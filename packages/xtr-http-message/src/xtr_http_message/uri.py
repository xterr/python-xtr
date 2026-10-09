"""A URI as a value: every component readable, every change a new instance.

A string is read as RFC 3986 defines a URI reference, and `uritools` does the
splitting — the five-part grammar of its appendix B, the scheme of §3.1, the
authority of §3.2. The standard library's splitter cannot be used for this: it
deletes a tab, a carriage return and a newline wherever it finds one, and trims
the blanks and control characters off both ends, all before anything of ours
sees the string, so it answers about a URI that was never asked about.
"""

from __future__ import annotations

import copy
import re
from ipaddress import IPv6Address
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self, final
from urllib.parse import quote

from typing_extensions import override
from uritools import uridefrag, urisplit
from xtr_http_message_contracts import UriInterface

from ._ascii import lower
from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from uritools import SplitResult

__all__ = ["Uri"]

# The schemes whose standard port is worth dropping from an authority.
_SCHEMES: Final[Mapping[str, int]] = MappingProxyType({"http": 80, "https": 443})

# The schemes that name a server to reach rather than a thing to look up, so
# that an authority with no host in it names nothing at all: RFC 9110 §4.2.1
# and §4.2.2 have a recipient reject such a reference instead of reading it.
_NEEDS_A_HOST: Final[frozenset[str]] = frozenset({"http", "https"})

_MAX_PORT = 0xFFFF

_CHAR_UNRESERVED = r"a-zA-Z0-9_\-\.~"
_CHAR_SUB_DELIMS = r"!\$&\'\(\)\*\+,;="
_CHAR_GEN_DELIMS = r":\/\?#\[\]@"

# RFC 3986 §3.2.2: ``reg-name = *( unreserved / pct-encoded / sub-delims )``.
# A registered name carries nothing else, so a blank, a tab, a control
# character or a stray per cent sign in one leaves a host nobody can look up.
_REG_NAME = re.compile(f"(?:[{_CHAR_UNRESERVED}{_CHAR_SUB_DELIMS}]|%[A-Fa-f0-9]{{2}})*")

# A run of delimiters in user information, which has to be encoded to stay
# inside the authority, or a per cent sign that does not open an escape —
# encoding one of those again would double it.
_IN_USER_INFO = re.compile(f"(?:[{_CHAR_GEN_DELIMS}{_CHAR_SUB_DELIMS}]+|%(?![A-Fa-f0-9]{{2}}))")
# A run of characters a path may not carry as it is, or a per cent sign that
# does not open an escape — encoding one of those again would double it.
_IN_PATH = re.compile(f"(?:[^{_CHAR_UNRESERVED}{_CHAR_SUB_DELIMS}%:@/]+|%(?![A-Fa-f0-9]{{2}}))")
# The same, for a query string or a fragment, where a question mark is data.
_IN_QUERY_OR_FRAGMENT = re.compile(
    f"(?:[^{_CHAR_UNRESERVED}{_CHAR_SUB_DELIMS}%:@/?]+|%(?![A-Fa-f0-9]{{2}}))"
)


def _encode(match: re.Match[str]) -> str:
    """Return the matched run of characters, per cent-encoded.

    Args:
        match: What one of the filter patterns matched.

    Returns:
        The run with every byte of its UTF-8 form escaped, except for the
        characters no URI ever needs escaped.
    """
    return quote(match[0], safe="")


def _unparseable(uri: str) -> InvalidArgumentError:
    """Return the error for a string that is not a URI.

    Args:
        uri: The string that could not be read as one.

    Returns:
        The error to raise, carrying the string it was raised over.
    """
    return InvalidArgumentError(f'Unable to parse URI: "{uri}"')


def _filter_path(path: str) -> str:
    """Return a path with everything that has to be encoded encoded, and nothing twice."""
    return _IN_PATH.sub(_encode, path)


def _filter_user_info(user_info: str) -> str:
    """Return user information encoded as RFC 3986 §3.2.1 writes it, and nothing twice.

    The first colon is the one the grammar keeps, between the user name and
    what follows it; a later one is data and goes the way of every other
    delimiter. Without this a user information read off a string would be
    written back out as it arrived, and an ``@`` or a bracket in it would move
    where the authority ends.

    Args:
        user_info: The user information, as the authority holds it.

    Returns:
        The user information, every delimiter and every broken escape in it
        per cent-encoded.
    """
    user, colon, rest = user_info.partition(":")
    encoded = _IN_USER_INFO.sub(_encode, user)
    if colon == "":
        return encoded

    return f"{encoded}:{_IN_USER_INFO.sub(_encode, rest)}"


def _filter_query_or_fragment(text: str) -> str:
    """Return a query string or fragment encoded the same way, and nothing twice."""
    return _IN_QUERY_OR_FRAGMENT.sub(_encode, text)


def _is_an_ip_literal(host: str) -> bool:
    """Tell whether what two brackets wrap is an address, as RFC 3986 §3.2.2 writes one.

    ``IP-literal = "[" ( IPv6address / IPvFuture ) "]"``, and the section says
    of that grammar that it "does not support IPv6 scoped addressing zone
    identifiers" — so a per cent sign between the brackets is a zone
    identifier or an escape with no business there, and neither names a host.
    An ``IPvFuture`` is a format announced by a version flag but left
    undefined, which §3.2.2 has an application report an error over rather
    than guess at: it is not an IPv6 address either, so it is refused here.

    Args:
        host: The host, brackets included.

    Returns:
        Whether the brackets wrap an address.
    """
    address = host[1:-1]
    if "%" in address:
        return False

    try:
        _ = IPv6Address(address)
    except ValueError:
        return False

    return True


def _is_a_host(host: str) -> bool:
    """Tell whether a string is a host, as RFC 3986 §3.2.2 writes one.

    Brackets are only ever there to wrap an IP-literal, so what they wrap has
    to be one; anything else is a registered name, which carries only
    unreserved characters, per cent escapes and sub-delimiters. Empty is a
    host too: §3.2.2 lets an authority name none.

    Args:
        host: The host, as an authority holds it.

    Returns:
        Whether it is one.
    """
    if host.startswith("[") and host.endswith("]"):
        return _is_an_ip_literal(host)

    return _REG_NAME.fullmatch(host) is not None


def _is_non_standard_port(scheme: str, port: int) -> bool:
    """Tell whether a port says anything the scheme does not already imply."""
    return _SCHEMES.get(scheme) != port


def _read_authority(parts: SplitResult[str], scheme: str, uri: str) -> tuple[str, str, int | None]:
    """Return the user information, host and port an authority names, each checked.

    RFC 3986 §3.2 reads an authority as ``[ userinfo "@" ] host [ ":" port ]``.
    The host is checked against §3.2.2 by :func:`_is_a_host`. The port is
    checked against §3.2.3, which allows digits and nothing else, an empty port
    meaning none; the range is the sixteen bits a TCP or UDP port is assigned
    from, as the contract refuses anything outside them. A port with no host in
    front of it is refused: §3.2 hangs the port off the host, so there is no
    authority to write it into.

    Args:
        parts: The URI reference as RFC 3986 appendix B splits it.
        scheme: The scheme already read off it, lowercased.
        uri: The whole string, which a refusal names.

    Returns:
        The user information, the host and the port — the first two empty and
        the last ``None`` where the URI names none of them.

    Raises:
        InvalidArgumentError: When the authority names something that is not a
            host or not a port, names a port with no host to belong to, or
            names no host under a scheme that needs one.
    """
    host = parts.host or ""

    if not _is_a_host(host):
        raise _unparseable(uri)

    # RFC 3986 §3.2.2 lets a host be empty; RFC 9110 §4.2.1 and §4.2.2 do not,
    # for the two schemes that name a server to reach.
    if host == "" and parts.authority is not None and scheme in _NEEDS_A_HOST:
        raise _unparseable(uri)

    port = parts.getport()
    # RFC 3986 §3.2.3 leaves the range to the scheme, and the split lets
    # nothing but digits through, so only the ceiling the contract sets — the
    # sixteen bits a TCP or UDP port is assigned from — can be broken.
    if port is not None and port > _MAX_PORT:
        raise _unparseable(uri)

    # A port belongs to the host it is written after, and with no host there is
    # no authority to write down at all (:meth:`Uri.get_authority`). Reading a
    # port off such a reference would leave an instance reporting one that no
    # text of its own could carry, so the reference is refused instead.
    if host == "" and port is not None:
        raise _unparseable(uri)

    return parts.userinfo or "", host, port


@final
class Uri(UriInterface):
    """A URI, taken apart into its components and put back together as text.

    Build one from a string and read any component off it; change one and get
    a new instance, since a URI is a value rather than a thing with a state:

    ```python
    from xtr_http_message import Uri

    uri = Uri("https://example.com/orders?page=2")
    assert uri.get_host() == "example.com"
    assert str(uri.with_path("/orders/7")) == "https://example.com/orders/7?page=2"
    ```

    Components arrive encoded or not, as the caller has them, and come back
    encoded exactly once. The standard port of the scheme is dropped, since it
    says nothing the scheme does not: ``Uri("https://example.com:443")`` has
    no port to report.

    A string is read as RFC 3986 defines a URI reference: a scheme opens with a
    letter (§3.1), a host is an IPv6 address in brackets — a grammar with no
    room for a zone identifier — or a registered name of unreserved
    characters, per cent escapes and sub-delimiters (§3.2.2), and a port is
    digits inside sixteen bits, written after a host (§3.2.3 and §3.2). A
    string that breaks one of those — ``http://exa mple.com``,
    ``http://[::1``, ``http://[fe80::1%eth0]``, ``http://h:65536``, ``//:80``
    — is refused, as is an ``http`` or ``https`` URI naming an authority with
    no host in it, such as ``http://`` (RFC 9110 §4.2.1 and §4.2.2). Nothing
    is trimmed and no character is dropped: whatever a path, a query string or
    a fragment may not carry as it is comes back per cent-encoded.

    Being read is not the same as being a URI reference. A string whose front
    is no scheme — ``ht tp://h/``, ``0:0`` — is read as a path and comes back
    per cent-encoded, and the result may still be no URI reference: §4.2
    leaves a colon out of the first segment of a relative-path one, so
    ``0:0`` would read as a scheme to somebody resolving it. Put ``./`` in
    front of such a path, or give the reference a scheme.
    """

    __slots__ = ("_fragment", "_host", "_path", "_port", "_query", "_scheme", "_user_info")

    def __init__(self, uri: str = "") -> None:
        """Read a URI out of a string, as RFC 3986 defines one.

        Args:
            uri: The URI. Empty — the default — builds one with no component
                at all, to be assembled through the ``with_*`` methods.

        Raises:
            InvalidArgumentError: When the string cannot be read as a URI
                reference — a host or a port that is not one, a port with no
                host to belong to, or no host under a scheme that needs one.
        """
        self._scheme: str = ""
        self._user_info: str = ""
        self._host: str = ""
        self._port: int | None = None
        self._path: str = ""
        self._query: str = ""
        self._fragment: str = ""

        if uri == "":
            return

        # RFC 3986 §3.5 puts the fragment behind the first ``#``, and it is cut
        # off first because the appendix B pattern reads the rest of the
        # reference but stops a fragment at a newline.
        head, fragment = uridefrag(uri)
        parts = urisplit(head)

        self._scheme = lower(parts.scheme or "")
        user_info, host, port = _read_authority(parts, self._scheme, uri)
        self._user_info = _filter_user_info(user_info)
        self._host = lower(host)
        # The scheme is recorded first: whether a port is worth keeping is
        # weighed against it.
        self._port = self._filter_port(port)
        self._path = _filter_path(parts.path)
        self._query = _filter_query_or_fragment(parts.query or "")
        self._fragment = _filter_query_or_fragment(fragment or "")

    @override
    def __str__(self) -> str:
        """Return the URI as text, either absolute or a relative reference.

        Never raises: a path that would read as something else once the other
        components are put in front of it is corrected rather than refused.

        Returns:
            The assembled URI.
        """
        return _assemble(
            self._scheme,
            self.get_authority(),
            self._path,
            self._query,
            self._fragment,
        )

    @override
    def get_scheme(self) -> str:
        """Return the scheme, lowercased, without its trailing colon.

        Returns:
            The scheme, or an empty string when the URI has none.
        """
        return self._scheme

    @override
    def get_authority(self) -> str:
        """Return the authority as ``[user-info@]host[:port]``.

        Returns:
            The authority, or an empty string when the URI has no host — user
            information without a host cannot be written down.
        """
        if self._host == "":
            return ""

        authority = self._host
        if self._user_info != "":
            authority = f"{self._user_info}@{authority}"
        if self._port is not None:
            authority = f"{authority}:{self._port}"

        return authority

    @override
    def get_user_info(self) -> str:
        """Return the user information as ``username[:password]``.

        Returns:
            The user information, or an empty string when the URI has none.
        """
        return self._user_info

    @override
    def get_host(self) -> str:
        """Return the host, lowercased.

        Returns:
            The host, or an empty string when the URI has none.
        """
        return self._host

    @override
    def get_port(self) -> int | None:
        """Return the port, when one is worth reporting.

        Returns:
            The port when it is not the standard one of the scheme, otherwise
            ``None``.
        """
        return self._port

    @override
    def get_path(self) -> str:
        """Return the path, percent-encoded.

        Two corrections are applied, so that the path read off a URI is one
        that can be used as it is: a rootless path gains a leading ``/`` when
        there is an authority to keep it apart from, and a path opening with
        more than one ``/`` has those reduced to one.

        Returns:
            The path.
        """
        path = self._path

        if path.startswith("//"):
            return "/" + path.lstrip("/")
        if path != "" and not path.startswith("/") and self._host != "":
            return f"/{path}"

        return path

    @override
    def get_query(self) -> str:
        """Return the query string, percent-encoded, without its leading ``?``.

        Returns:
            The query string, or an empty string when the URI has none.
        """
        return self._query

    @override
    def get_fragment(self) -> str:
        """Return the fragment, percent-encoded, without its leading ``#``.

        Returns:
            The fragment, or an empty string when the URI has none.
        """
        return self._fragment

    @override
    def with_scheme(self, scheme: str) -> Self:
        """Return an instance carrying ``scheme``.

        A port that was non-standard for the old scheme may be standard for
        the new one, so the port is weighed again.

        Args:
            scheme: The scheme the new instance carries, in any case. Empty
                removes the scheme.

        Returns:
            A new instance, or this one when the scheme is already that.
        """
        scheme = lower(scheme)
        if self._scheme == scheme:
            return self

        new = self._copy()
        new._scheme = scheme  # noqa: SLF001 — a copy of this very class.
        new._port = new._filter_port(new._port)  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_user_info(self, user: str, password: str | None = None) -> Self:
        """Return an instance carrying ``user`` and, optionally, ``password``.

        Args:
            user: The user name. Empty with no password removes the user
                information; empty with a password keeps the password under a
                user name that is empty, which is what ``:pass`` says.
            password: The password that goes with ``user``, when there is one.

        Returns:
            A new instance, or this one when the user information is already
            that.
        """
        info = _IN_USER_INFO.sub(_encode, user)
        if password is not None and password != "":
            info = f"{info}:{_IN_USER_INFO.sub(_encode, password)}"

        if self._user_info == info:
            return self

        new = self._copy()
        new._user_info = info  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_host(self, host: str) -> Self:
        """Return an instance carrying ``host``.

        Args:
            host: The host, in any case. Empty removes the host.

        Returns:
            A new instance, or this one when the host is already that.

        Raises:
            InvalidArgumentError: When the host is not one as RFC 3986 §3.2.2
                writes it. That grammar is ASCII throughout, so a name in
                another script is given in its ``xn--`` form — and a ``Host``
                header is written straight off this component, which is the
                other reason nothing else may reach it.
        """
        host = lower(host)
        if not _is_a_host(host):
            message = f'Invalid host: "{host}". Must be an address in brackets or a registered name'
            raise InvalidArgumentError(message)

        if self._host == host:
            return self

        new = self._copy()
        new._host = host  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_port(self, port: int | None) -> Self:
        """Return an instance carrying ``port``.

        Args:
            port: The port, or ``None`` to remove it. The standard port of the
                current scheme is taken as ``None``.

        Returns:
            A new instance, or this one when the port is already that.

        Raises:
            InvalidArgumentError: When the port falls outside the range a TCP
                or UDP port is assigned from.
        """
        filtered = self._filter_port(port)
        if self._port == filtered:
            return self

        new = self._copy()
        new._port = filtered  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_path(self, path: str) -> Self:
        """Return an instance carrying ``path``.

        Args:
            path: The path, encoded or not. It may be empty, absolute, or
                rootless.

        Returns:
            A new instance, or this one when the path is already that.
        """
        path = _filter_path(path)
        if self._path == path:
            return self

        new = self._copy()
        new._path = path  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_query(self, query: str) -> Self:
        """Return an instance carrying ``query``.

        Args:
            query: The query string, encoded or not, without a leading ``?``
                unless that question mark is data. Empty removes it.

        Returns:
            A new instance, or this one when the query string is already that.
        """
        query = _filter_query_or_fragment(query)
        if self._query == query:
            return self

        new = self._copy()
        new._query = query  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def with_fragment(self, fragment: str) -> Self:
        """Return an instance carrying ``fragment``.

        Args:
            fragment: The fragment, encoded or not, without a leading ``#``
                unless that hash is data. Empty removes it.

        Returns:
            A new instance, or this one when the fragment is already that.
        """
        fragment = _filter_query_or_fragment(fragment)
        if self._fragment == fragment:
            return self

        new = self._copy()
        new._fragment = fragment  # noqa: SLF001 — a copy of this very class.

        return new

    def _copy(self) -> Self:
        """Return a copy to change, leaving this instance as it is.

        Every component is a string or a number, so a shallow copy shares
        nothing that could be changed through it.
        """
        return copy.copy(self)

    def _filter_port(self, port: int | None) -> int | None:
        """Return a port worth keeping, weighed against the current scheme.

        Args:
            port: The port to weigh, or ``None``.

        Returns:
            The port when the scheme does not already imply it, otherwise
            ``None``.

        Raises:
            InvalidArgumentError: When the port falls outside the range a TCP
                or UDP port is assigned from.
        """
        if port is None:
            return None

        if port < 0 or port > _MAX_PORT:
            message = f"Invalid port: {port}. Must be between 0 and 65535"
            raise InvalidArgumentError(message)

        return port if _is_non_standard_port(self._scheme, port) else None


def _assemble(scheme: str, authority: str, path: str, query: str, fragment: str) -> str:
    """Put a URI back together from its components.

    The path is corrected where joining it to the components in front of it
    would read as something else: a rootless path after an authority gains a
    leading ``/``, and a path opening with more than one ``/`` with no
    authority in front of it has those reduced to one — otherwise it would
    read as an authority itself.

    Args:
        scheme: The scheme, or empty.
        authority: The authority, or empty.
        path: The path, as it is held rather than as :meth:`Uri.get_path`
            reports it.
        query: The query string, or empty.
        fragment: The fragment, or empty.

    Returns:
        The assembled URI.
    """
    uri = f"{scheme}:" if scheme != "" else ""

    if authority != "":
        uri = f"{uri}//{authority}"

    if path != "":
        if path.startswith("//") and authority == "":
            path = "/" + path.lstrip("/")
        elif not path.startswith("/") and authority != "":
            path = f"/{path}"
        uri = f"{uri}{path}"

    if query != "":
        uri = f"{uri}?{query}"

    if fragment != "":
        uri = f"{uri}#{fragment}"

    return uri
