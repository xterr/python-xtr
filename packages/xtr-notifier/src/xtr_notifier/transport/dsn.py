"""Reading the DSN that picks a transport and configures it.

A notifier DSN names a provider by its scheme and carries everything the
provider needs in one string an application can keep in its environment::

    slack://TOKEN@default?channel=ops
    telegram://BOT_ID:TOKEN@default?channel=CHAT_ID
    null://null

The host is required — ``default`` stands for the provider's own API host —
so a DSN with nothing after the scheme is refused rather than guessed at.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final, overload
from urllib.parse import parse_qsl, unquote, urlsplit

from typing_extensions import override

from xtr_notifier.exception import InvalidArgumentError, MissingRequiredOptionError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Dsn"]

_TRUE = frozenset({"1", "true", "on", "yes"})
_FALSE = frozenset({"0", "false", "off", "no", ""})


@final
class Dsn:
    """A parsed notifier DSN.

    The scheme and the host keep the case they were written in: a transport's
    string form and the errors naming a scheme show what the application
    configured, not a normalised copy of it. The user and the password are
    percent-decoded, so a token holding a reserved character is written
    escaped and read back whole.
    """

    __slots__ = (
        "_host",
        "_options",
        "_original_dsn",
        "_password",
        "_path",
        "_port",
        "_scheme",
        "_user",
    )

    def __init__(self, dsn: str) -> None:
        """Read ``dsn`` into its parts.

        Args:
            dsn: The DSN as configured.

        Raises:
            InvalidArgumentError: If ``dsn`` cannot be read as a URL, carries no
                scheme, or carries no host.
        """
        self._original_dsn = dsn
        try:
            split = urlsplit(dsn)
            port = split.port
        except ValueError as error:
            raise InvalidArgumentError("The notifier DSN is invalid.") from error
        if not split.scheme:
            raise InvalidArgumentError("The notifier DSN must contain a scheme.")
        if not (split.netloc or split.path or split.query):
            # Nothing at all after the scheme: there is no URL here to read a host from.
            raise InvalidArgumentError("The notifier DSN is invalid.")
        host = _host_of(split.netloc)
        if not host:
            raise InvalidArgumentError(
                'The notifier DSN must contain a host (use "default" by default).'
            )
        # urlsplit lowercases the scheme; the DSN as written keeps the case.
        self._scheme = dsn[: len(split.scheme)]
        self._host = host
        self._user = unquote(split.username) if split.username else None
        self._password = unquote(split.password) if split.password else None
        self._port = port
        self._path = split.path or None
        self._options: Mapping[str, str] = MappingProxyType(
            dict(parse_qsl(split.query, keep_blank_values=True))
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

    @property
    def port(self) -> int | None:
        """The port, or ``None`` when the DSN names none."""
        return self._port

    @property
    def path(self) -> str | None:
        """The path, or ``None`` when the DSN has none."""
        return self._path

    @property
    def options(self) -> Mapping[str, str]:
        """The query options, in the order they were written."""
        return self._options

    @property
    def original_dsn(self) -> str:
        """The DSN as configured, credentials included: never log it."""
        return self._original_dsn

    @overload
    def get_option(self, key: str) -> str | None: ...
    @overload
    def get_option(self, key: str, default: str) -> str: ...
    @overload
    def get_option(self, key: str, default: str | None) -> str | None: ...
    def get_option(self, key: str, default: str | None = None) -> str | None:
        """Return the option ``key``, or ``default`` when the DSN does not set it."""
        return self._options.get(key, default)

    def get_required_option(self, key: str) -> str:
        """Return the option ``key``, which must be set and not blank.

        Raises:
            MissingRequiredOptionError: If the option is missing or blank.
        """
        value = self._options.get(key)
        if value is None or not value.strip():
            raise MissingRequiredOptionError(key)
        return value

    def get_boolean_option(self, key: str, default: bool = False) -> bool:
        """Return the option ``key`` read as a boolean, or ``default`` when it is not set.

        ``1``, ``true``, ``on`` and ``yes`` are true; ``0``, ``false``, ``off``,
        ``no`` and an empty value are false, in any case.

        Raises:
            InvalidArgumentError: If the value is none of those. A typo such as
                ``ssl=ture`` would otherwise quietly turn an option off.
        """
        value = self._options.get(key)
        if value is None:
            return default
        normalised = value.strip().lower()
        if normalised in _TRUE:
            return True
        if normalised in _FALSE:
            return False
        raise InvalidArgumentError(f'Value "{value}" of the "{key}" DSN option is not a boolean.')

    @override
    def __repr__(self) -> str:
        """Render without the credentials, which a traceback would otherwise leak."""
        return (
            f"{type(self).__name__}(scheme={self._scheme!r}, host={self._host!r}, "
            f"port={self._port!r}, path={self._path!r}, options={dict(self._options)!r})"
        )


def _host_of(netloc: str) -> str:
    """Return the host of ``netloc`` as written: no credentials, no port, brackets kept."""
    authority = netloc.rpartition("@")[2]
    if authority.startswith("["):
        return authority.partition("]")[0] + "]"
    return authority.partition(":")[0]
