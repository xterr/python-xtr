"""Reading the DSN that picks a mail transport and configures it.

A mailer DSN names a transport by its scheme and carries everything it needs
in one string an application can keep in its environment::

    smtp://user:pass@smtp.example.com:587?verify_peer=0
    sendmail://default
    mailgun+api://KEY:DOMAIN@default?region=eu
    null://null

The host is required — ``default`` stands for the provider's own host — so a
DSN with nothing after the scheme is refused rather than guessed at.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeAlias, TypeVar, final, overload
from urllib.parse import parse_qsl, unquote, urlsplit

from typing_extensions import override

from xtr_mailer._error_text import option_value
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from re import Pattern
    from urllib.parse import SplitResult

__all__ = ["Dsn", "DsnOption"]

#: What an option of the query string holds: ``key=v`` a string, ``key[]=a&key[]=b`` the
#: strings in order, ``key[name]=v`` the strings by name.
DsnOption: TypeAlias = str | tuple[str, ...] | Mapping[str, str]

_T = TypeVar("_T")

_TRUE = frozenset({"1", "true", "on", "yes"})
_FALSE = frozenset({"0", "false", "off", "no", ""})
_BRACKETED: Pattern[str] = re.compile(r"([^\[\]]+)\[([^\[\]]*)\]")
_CONTROL: Pattern[str] = re.compile(r"[\x00-\x1f\x7f]")


@final
class Dsn:
    """A parsed mailer DSN.

    The scheme and the host keep the case they were written in: the errors
    naming a scheme show what the application configured, not a normalised copy
    of it. The user and the password are percent-decoded, so a password holding a
    reserved character is written escaped and read back whole; an empty one is
    ``None``, as if it were not written.
    """

    __slots__ = ("_host", "_options", "_password", "_port", "_scheme", "_user")

    def __init__(  # noqa: PLR0913, PLR0917 - the six parts a DSN is made of, in their order
        self,
        scheme: str,
        host: str,
        user: str | None = None,
        password: str | None = None,
        port: int | None = None,
        options: Mapping[str, DsnOption | None] | None = None,
    ) -> None:
        """Assemble a DSN from its parts, as :meth:`from_string` does once it has read them.

        Args:
            scheme: What a factory dispatches on.
            host: The host, ``default`` standing for the provider's own.
            user: The decoded user, or ``None``.
            password: The decoded password, or ``None``.
            port: The port, or ``None`` for the transport's own.
            options: The query options; an option set to ``None`` reads as unset.
        """
        self._scheme = scheme
        self._host = host
        self._user = user
        self._password = password
        self._port = port
        # A named option is copied into a read-only view: nothing handed in or out can change it.
        self._options: Mapping[str, DsnOption | None] = MappingProxyType(
            {
                key: MappingProxyType(dict(value)) if isinstance(value, Mapping) else value
                for key, value in (options or {}).items()
            }
        )

    @classmethod
    def from_string(cls, dsn: str) -> Dsn:
        """Read ``dsn`` into its parts.

        Args:
            dsn: The DSN as configured. It carries credentials: it is never kept,
                and no error raised here quotes it or chains an error that does.
                Whitespace around it is ignored, as an environment file often adds some.

        Raises:
            InvalidArgumentError: If ``dsn`` cannot be read as a URL, carries a
                control character inside it, carries no scheme, or carries no host.
        """
        dsn = dsn.strip()
        # The URL reader drops tabs and line breaks and keeps the other control characters: a
        # DSN it would have to mend, or that would carry one to a server, is refused rather
        # than read as something it does not say.
        if _CONTROL.search(dsn) is not None:
            raise InvalidArgumentError("The mailer DSN is invalid.")
        parts = _split_or_none(dsn)
        if parts is None:
            raise InvalidArgumentError("The mailer DSN is invalid.")
        split, port = parts
        if not split.scheme:
            raise InvalidArgumentError("The mailer DSN must contain a scheme.")
        # urlsplit lowercases the scheme; the DSN as written keeps the case.
        scheme = dsn.partition(":")[0]
        if not (split.netloc or split.path or split.query):
            # Nothing at all after the scheme: there is no URL here to read a host from.
            raise InvalidArgumentError("The mailer DSN is invalid.")
        host = _host_of(split.netloc)
        if not host:
            raise InvalidArgumentError(
                'The mailer DSN must contain a host (use "default" by default).'
            )
        return cls(
            scheme,
            host,
            unquote(split.username) if split.username else None,
            unquote(split.password) if split.password else None,
            port,
            _options_of(split.query),
        )

    @property
    def scheme(self) -> str:
        """What a factory dispatches on, as written."""
        return self._scheme

    @property
    def host(self) -> str:
        """The host, ``default`` standing for the provider's own."""
        return self._host

    @property
    def user(self) -> str | None:
        """The decoded user, or ``None`` when the DSN carries none."""
        return self._user

    @property
    def password(self) -> str | None:
        """The decoded password, or ``None`` when the DSN carries none."""
        return self._password

    def get_port(self, default: int | None = None) -> int | None:
        """Return the port, or ``default`` — the transport's own — when the DSN names none."""
        return default if self._port is None else self._port

    @overload
    def get_option(self, key: str) -> DsnOption | None: ...
    @overload
    def get_option(self, key: str, default: _T) -> DsnOption | _T: ...
    def get_option(self, key: str, default: object = None) -> object:
        """Return the option ``key``, or ``default`` when the DSN does not set it."""
        value = self._options.get(key)
        return default if value is None else value

    def get_boolean_option(self, key: str, default: bool = False) -> bool:
        """Return the option ``key`` read as a boolean, or ``default`` when it is not set.

        ``1``, ``true``, ``on`` and ``yes`` are true; ``0``, ``false``, ``off``,
        ``no`` and an empty value are false, in any case.

        Raises:
            InvalidArgumentError: If the value is none of those. A typo such as
                ``verify_peer=fasle`` would otherwise quietly read as false. The value is
                quoted only when it is one plain word.
        """
        match self._options.get(key):
            case None:
                return default
            case str() as value:
                normalised = value.strip().lower()
                if normalised in _TRUE:
                    return True
                if normalised in _FALSE:
                    return False
                shown = option_value(value)
            case tuple():
                shown = "list"
            case _:
                shown = "mapping"
        if shown is None:
            raise InvalidArgumentError(f'The value of the "{key}" DSN option is not a boolean.')
        raise InvalidArgumentError(f'Value "{shown}" of the "{key}" DSN option is not a boolean.')

    @override
    def __repr__(self) -> str:
        """Render without the credentials, which a traceback or a log would otherwise leak."""
        # A named option is shown as the plain dict it holds, not as its read-only view.
        options = {
            key: dict(value) if isinstance(value, Mapping) else value
            for key, value in self._options.items()
        }
        return (
            f"{type(self).__name__}(scheme={self._scheme!r}, host={self._host!r}, "
            f"port={self._port!r}, options={options!r})"
        )


def _split_or_none(dsn: str) -> tuple[SplitResult, int | None] | None:
    """Split ``dsn`` and read its port, or return ``None`` when the URL is malformed.

    The stdlib error quotes the netloc, credentials included, so it is dropped here: the
    caller raises its own error once this has returned, outside any handler, so no error
    is chained as the context of the one it raises.
    """
    try:
        split = urlsplit(dsn)
        port = split.port
    except ValueError:
        return None
    return split, port


def _host_of(netloc: str) -> str:
    """Return the host of ``netloc`` as written: no credentials, no port, brackets kept."""
    authority = netloc.rpartition("@")[2]
    if authority.startswith("["):
        return authority.partition("]")[0] + "]"
    return authority.partition(":")[0]


def _options_of(query: str) -> dict[str, DsnOption]:
    """Read the query string, ``key[]`` collecting a list and ``key[name]`` a mapping."""
    options: dict[str, DsnOption] = {}
    for key, value in parse_qsl(query, keep_blank_values=True):
        bracketed = _BRACKETED.fullmatch(key)
        if bracketed is None:
            options[key] = value
            continue
        name, index = bracketed.groups()
        current = options.get(name)
        if index:
            named = dict(current) if isinstance(current, Mapping) else {}
            named[index] = value
            options[name] = named
        else:
            listed = current if isinstance(current, tuple) else ()
            options[name] = (*listed, value)
    return options
