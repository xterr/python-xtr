"""A URI, taken apart into its components and put back together as text."""

from __future__ import annotations

from typing import Protocol, Self, runtime_checkable

from typing_extensions import override

__all__ = ["UriInterface"]


@runtime_checkable
class UriInterface(Protocol):
    """A URI as a value: every component readable, every change a new instance.

    Its first use is the target of a request, but nothing here is bound to
    that — any URI fits. A request usually carries the host in a ``Host``
    header as well, and a server-side request usually finds the scheme among
    its server parameters.

    Instances are immutable. Every ``with_*`` method keeps the instance it was
    called on as it was and returns one carrying the change.
    """

    def get_scheme(self) -> str:
        """Return the scheme, lowercased, without its trailing colon.

        Returns:
            The scheme, or an empty string when the URI has none.
        """
        ...

    def get_authority(self) -> str:
        """Return the authority as ``[user-info@]host[:port]``.

        The port is left out when it is not set, and should be left out when
        it is the standard port of the current scheme.

        Returns:
            The authority, or an empty string when the URI has none.
        """
        ...

    def get_user_info(self) -> str:
        """Return the user information as ``username[:password]``.

        The password is appended after a colon only when there is one. The
        trailing ``@`` belongs to the authority, not here, and is never added.

        Returns:
            The user information, or an empty string when the URI has none.
        """
        ...

    def get_host(self) -> str:
        """Return the host, lowercased.

        Returns:
            The host, or an empty string when the URI has none.
        """
        ...

    def get_port(self) -> int | None:
        """Return the port, when one is worth reporting.

        A port that is non-standard for the current scheme comes back as an
        integer. The standard port of the current scheme should come back as
        ``None``, since it adds nothing.

        With no port and no scheme, the answer is always ``None``. With no
        port but a scheme, an implementation may answer with that scheme's
        standard port, though ``None`` is the better answer.

        Returns:
            The port, or ``None``.
        """
        ...

    def get_path(self) -> str:
        """Return the path, percent-encoded.

        A path may be empty, absolute (opening with a slash), or rootless (not
        opening with a slash); all three are supported.

        The empty path and ``"/"`` are elsewhere treated as the same thing,
        but this method must not normalise one into the other: where a base
        path has been trimmed off, the difference matters, and telling the two
        apart is the caller's job.

        Characters that have to be encoded are encoded, and never encoded
        twice. A slash meant as data rather than as a segment separator must
        therefore reach the instance already written as ``%2F``.

        Returns:
            The path.
        """
        ...

    def get_query(self) -> str:
        """Return the query string, percent-encoded, without its leading ``?``.

        Characters that have to be encoded are encoded, and never encoded
        twice. An ampersand meant as data rather than as a separator must
        therefore reach the instance already written as ``%26``.

        Returns:
            The query string, or an empty string when the URI has none.
        """
        ...

    def get_fragment(self) -> str:
        """Return the fragment, percent-encoded, without its leading ``#``.

        Characters that have to be encoded are encoded, and never encoded
        twice.

        Returns:
            The fragment, or an empty string when the URI has none.
        """
        ...

    def with_scheme(self, scheme: str) -> Self:
        """Return an instance carrying ``scheme``.

        ``http`` and ``https`` are supported whatever their case; other
        schemes may be. An empty scheme removes the scheme.

        Args:
            scheme: The scheme the new instance carries.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the scheme is malformed or unsupported.
        """
        ...

    def with_user_info(self, user: str, password: str | None = None) -> Self:
        """Return an instance carrying ``user`` and, optionally, ``password``.

        A password without a user cannot be expressed: an empty ``user``
        removes the user information entirely.

        Args:
            user: The user name of the authority.
            password: The password that goes with ``user``, when there is one.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def with_host(self, host: str) -> Self:
        """Return an instance carrying ``host``.

        An empty host removes the host.

        Args:
            host: The host the new instance carries.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the host is not a valid host name.
        """
        ...

    def with_port(self, port: int | None) -> Self:
        """Return an instance carrying ``port``.

        ``None`` removes the port.

        Args:
            port: The port the new instance carries, or ``None``.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the port falls outside the range a TCP or UDP
                port is assigned from.
        """
        ...

    def with_path(self, path: str) -> Self:
        """Return an instance carrying ``path``.

        A path may be empty, absolute (opening with a slash), or rootless (not
        opening with a slash); all three are supported. A path meant to be
        relative to the host rather than to a base path has to open with a
        slash, since one that does not is taken as relative to a base path the
        application knows about.

        Characters may be given encoded or not; the instance sees to the
        encoding :meth:`get_path` describes.

        Args:
            path: The path the new instance carries.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the path is malformed.
        """
        ...

    def with_query(self, query: str) -> Self:
        """Return an instance carrying ``query``.

        Characters may be given encoded or not; the instance sees to the
        encoding :meth:`get_query` describes. An empty query string removes
        the query string.

        Args:
            query: The query string the new instance carries.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the query string is malformed.
        """
        ...

    def with_fragment(self, fragment: str) -> Self:
        """Return an instance carrying ``fragment``.

        Characters may be given encoded or not; the instance sees to the
        encoding :meth:`get_fragment` describes. An empty fragment removes the
        fragment.

        Args:
            fragment: The fragment the new instance carries.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    @override
    def __str__(self) -> str:
        """Return the URI as text, either absolute or a relative reference.

        Which of the two comes out depends on which components are present.
        They are joined with the delimiters that belong between them:

        - a scheme, when present, is followed by ``:``;
        - an authority, when present, is preceded by ``//``;
        - the path is appended as it is, except for two corrections that keep
          the result a valid reference, since this method must not raise:

          - a rootless path with an authority present gains a leading ``/``;
          - a path opening with more than one ``/`` and no authority present
            has those leading slashes reduced to one;

        - a query, when present, is preceded by ``?``;
        - a fragment, when present, is preceded by ``#``.

        Returns:
            The assembled URI.
        """
        ...
