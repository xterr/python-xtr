"""Finding the transport factory that serves a DSN scheme.

Factories are discovered, not listed. A provider library advertises its
factory under one of two entry point groups — the chatter's, for chat
providers, or the texter's, for SMS and push providers — one entry per DSN
scheme, each naming the factory **class**::

    [project.entry-points."xtr_notifier.chatter_transport_factories"]
    telegram = "xtr_telegram_notifier:TelegramTransportFactory"

**The entry point name is the DSN scheme it serves.** That keeps resolution
lazy: a ``telegram://`` DSN loads the Telegram library and nothing else. The
split by kind keeps a chat provider out of the texter: ``slack://`` among the
texter's DSNs is an unsupported scheme, not a chat message sent as an SMS.

**A discovered factory is built with keywords** ``http_client=`` and
``event_dispatcher=`` — the constructor of
:class:`~xtr_notifier.transport.abstract_transport_factory.AbstractTransportFactory`,
which every provider factory inherits. A factory needing any other
collaborator cannot be discovered; pass it to the
:class:`~xtr_notifier.transport.transport.Transport` builder yourself, or
register it through the notifier bundle.
"""

from __future__ import annotations

import inspect
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Final, final

from xtr_notifier.exception import LogicError

from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from importlib.metadata import EntryPoint

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

    from .dsn import Dsn

__all__ = ["TransportFactoryDiscovery"]

_HTTP_CLIENT = "http_client"


@final
class TransportFactoryDiscovery:
    """Finds and builds the factory an installed library advertises for a scheme.

    One discovery reads one group: the chatter's or the texter's. It is handed
    the collaborators every factory it builds receives; without an HTTP client
    it still builds a factory that needs none (``null://``), and refuses — with
    an error naming the scheme — one that does.
    """

    #: The group chat providers advertise their factories under.
    CHATTER_GROUP: Final = "xtr_notifier.chatter_transport_factories"
    #: The group SMS and push providers advertise their factories under.
    TEXTER_GROUP: Final = "xtr_notifier.texter_transport_factories"

    __slots__ = ("_event_dispatcher", "_group", "_http_client")

    def __init__(
        self,
        group: str,
        *,
        http_client: HttpClientInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Discover the factories advertised under ``group``.

        Args:
            group: The entry point group to read, usually :attr:`CHATTER_GROUP`
                or :attr:`TEXTER_GROUP`.
            http_client: Handed to every factory built; ``None`` when the
                application has none, which only factories needing none survive.
            event_dispatcher: Handed to every factory built.
        """
        self._group = group
        self._http_client = http_client
        self._event_dispatcher = event_dispatcher

    @property
    def name(self) -> str:
        """What the group serves — ``chatter`` or ``texter`` — or the group itself."""
        return {self.CHATTER_GROUP: "chatter", self.TEXTER_GROUP: "texter"}.get(
            self._group, self._group
        )

    def advertised_schemes(self) -> tuple[str, ...]:
        """Return every scheme an installed library advertises in the group, sorted.

        Advertised is not usable: a scheme whose library cannot be imported is
        listed here and still yields no factory.
        """
        return tuple(sorted({entry.name for entry in entry_points(group=self._group)}))

    def factory_for(self, dsn: Dsn) -> TransportFactoryInterface | None:
        """Return the factory serving ``dsn``, importing only the libraries advertising its scheme.

        Returns ``None`` when no library advertises the scheme, or none that does
        can be loaded.

        Raises:
            LogicError: If the factory serving the scheme needs an HTTP client
                and this discovery was given none.
        """
        for entry in entry_points(group=self._group, name=dsn.scheme):
            factory = self._build(entry)
            if factory is not None and factory.supports(dsn):
                return factory
        return None

    def _build(self, entry: EntryPoint) -> TransportFactoryInterface | None:
        """Build one advertised factory, or return ``None`` when it is unusable.

        The entry point is loaded through a reference typed to return
        ``object`` so nothing untyped escapes, and the result is checked
        against the protocol: a library advertising something that is not a
        transport factory is skipped rather than breaking every other scheme.
        """
        load: Callable[[], object] = entry.load
        try:
            advertised = load()
        except ImportError:
            return None
        if not (inspect.isclass(advertised) and issubclass(advertised, TransportFactoryInterface)):
            return None
        keywords: dict[str, object] = {"event_dispatcher": self._event_dispatcher}
        if self._http_client is not None:
            keywords[_HTTP_CLIENT] = self._http_client
        elif _needs_http_client(advertised):
            raise LogicError(
                f'The "{entry.name}" transport needs an HTTP client; build the transports with one.'
            )
        made = _construct(advertised, keywords)
        return made if isinstance(made, TransportFactoryInterface) else None


def _needs_http_client(factory_class: type) -> bool:
    """Tell whether ``factory_class`` cannot be built without an ``http_client``."""
    try:
        _ = inspect.signature(factory_class).bind(event_dispatcher=None)
    except TypeError:
        return True
    return False


def _construct(factory_class: Callable[..., object], keywords: Mapping[str, object]) -> object:
    """Build ``factory_class`` with ``keywords``, whatever its declared constructor."""
    return factory_class(**keywords)
