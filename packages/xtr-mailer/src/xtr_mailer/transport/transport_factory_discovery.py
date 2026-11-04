"""Finding the transport factory that serves a DSN scheme.

Factories are discovered, not listed. A library advertises its factory under one entry point
group, one entry per DSN scheme, each naming the factory **class**::

    [project.entry-points."xtr_mailer.transport_factories"]
    mailgun = "xtr_mailgun_mailer:MailgunTransportFactory"
    "mailgun+api" = "xtr_mailgun_mailer:MailgunTransportFactory"

**The entry point name is the DSN scheme it serves.** That keeps resolution lazy: a
``mailgun+api://`` DSN loads the Mailgun library and nothing else. This package advertises its
own built-in factories the same way, ``null`` among them.

**A discovered factory is built with keywords** ``event_dispatcher=``, ``http_client=`` and
``logger=`` — the constructor of
:class:`~xtr_mailer.transport.AbstractTransportFactory`, which every factory inherits. A
factory needing any other collaborator cannot be discovered; hand it to the
:class:`~xtr_mailer.transport.Transport` builder yourself.
"""

from __future__ import annotations

import inspect
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Final, final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import LogicError

from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from importlib.metadata import EntryPoint

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

    from .dsn import Dsn

__all__ = ["TransportFactoryDiscovery"]

#: The keywords every discovered factory is built with.
_KEYWORDS: Final = ("event_dispatcher", "http_client", "logger")


@final
class TransportFactoryDiscovery:
    """Finds and builds the factory an installed library advertises for a scheme.

    It is handed the collaborators every factory it builds receives. Without an HTTP client it
    still builds a factory that needs none (``null://``), and refuses — with an error naming
    the scheme — one that does.

    The factory found for a scheme is kept and serves every later DSN of that scheme: reading
    the installed entry points costs a scan of every installed distribution, which a DSN
    string grouping many DSNs must not pay once per DSN.
    """

    #: The group transport factories are advertised under.
    GROUP: Final = "xtr_mailer.transport_factories"

    __slots__ = ("_event_dispatcher", "_found", "_http_client", "_logger")

    def __init__(
        self,
        *,
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Discover the advertised factories, building each with these collaborators.

        Args:
            event_dispatcher: Handed to every factory built.
            http_client: Handed to every factory built; ``None`` when the application has
                none, which only factories needing none survive.
            logger: Handed to every factory built.
        """
        self._event_dispatcher = event_dispatcher
        self._http_client = http_client
        self._logger = logger
        self._found: dict[str, TransportFactoryInterface | None] = {}

    def advertised_schemes(self) -> tuple[str, ...]:
        """Return every scheme an installed library advertises, sorted.

        Advertised is not usable: a scheme whose library cannot be imported is listed here and
        still yields no factory.
        """
        return tuple(sorted({entry.name for entry in entry_points(group=self.GROUP)}))

    def factory_for(self, dsn: Dsn) -> TransportFactoryInterface | None:
        """Return the factory serving ``dsn``, importing only the libraries advertising its scheme.

        Returns ``None`` when no library advertises the scheme, or none that does can be loaded
        or serves it.

        Raises:
            LogicError: The factory serving the scheme needs an HTTP client and this discovery
                was given none.
        """
        if dsn.scheme not in self._found:
            self._found[dsn.scheme] = self._find(dsn)
        return self._found[dsn.scheme]

    def _find(self, dsn: Dsn) -> TransportFactoryInterface | None:
        """Build the first factory advertised for ``dsn``'s scheme that serves it."""
        for entry in entry_points(group=self.GROUP, name=dsn.scheme):
            factory = self._build(entry)
            if factory is not None and factory.supports(dsn):
                return factory
        return None

    def _build(self, entry: EntryPoint) -> TransportFactoryInterface | None:
        """Build one advertised factory, or return ``None`` when it is unusable.

        The entry point is loaded through a reference typed to return ``object`` so nothing
        untyped escapes, and the result is checked against the protocol: a library advertising
        something that is not a transport factory is skipped rather than breaking every other
        scheme. One naming a module or a class that is not there is skipped the same way, and
        nothing of the import error is kept, so the scheme reads as unsupported.

        Raises:
            LogicError: The factory cannot be built with the discovery keywords, or needs an
                HTTP client this discovery was not given.
        """
        load: Callable[[], object] = entry.load
        try:
            advertised = load()
        except (ImportError, AttributeError):
            return None
        if not (inspect.isclass(advertised) and issubclass(advertised, TransportFactoryInterface)):
            return None
        # Checked before building, outside any handler, so no TypeError is chained to the error.
        if not _accepts(advertised, _KEYWORDS):
            raise LogicError(
                f'The "{shown(entry.name)}" transport factory cannot be built with the keywords '
                '"event_dispatcher", "http_client" and "logger".'
            )
        keywords: dict[str, object] = {
            "event_dispatcher": self._event_dispatcher,
            "logger": self._logger,
        }
        if self._http_client is not None:
            keywords["http_client"] = self._http_client
        elif not _accepts(advertised, keywords):
            raise LogicError(
                f'The "{shown(entry.name)}" transport needs an HTTP client; '
                "build the transports with one."
            )
        made = _construct(advertised, keywords)
        return made if isinstance(made, TransportFactoryInterface) else None


def _accepts(factory_class: type, keywords: Iterable[str]) -> bool:
    """Tell whether ``factory_class`` can be built with exactly ``keywords``."""
    try:
        _ = inspect.signature(factory_class).bind(**dict.fromkeys(keywords))
    except TypeError:
        return False
    return True


def _construct(factory_class: Callable[..., object], keywords: Mapping[str, object]) -> object:
    """Build ``factory_class`` with ``keywords``, whatever its declared constructor."""
    return factory_class(**keywords)
