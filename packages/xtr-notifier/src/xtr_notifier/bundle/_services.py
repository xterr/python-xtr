"""The services the notifier bundle has the container build.

Each factory's parameters are read at runtime by the container, so the types
they name are imported here, not only for type checking. A factory serving one
kind — chat, or SMS and push — is made by a function taking the kind, its
qualifiers written onto it as annotations.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Final, final

from xtr_dependency_injection import ServiceLocator, Target

from xtr_notifier.channel import (
    ChannelInterface,
    ChannelPolicy,
    ChatChannel,
    PushChannel,
    SmsChannel,
)
from xtr_notifier.chatter import Chatter
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.exception import LogicError
from xtr_notifier.notifier import Notifier
from xtr_notifier.recipient import Recipient
from xtr_notifier.texter import Texter
from xtr_notifier.transport import (
    AbstractTransportFactory,
    Transport,
    TransportFactoryDiscovery,
    TransportFactoryInterface,
    Transports,
)

from ._peers import EventDispatcherPeer, HttpClientPeer, MessageBusPeer
from .notifier_config import NotifierConfig

__all__ = [
    "CHATTER",
    "TEXTER",
    "Kind",
    "chat_channel",
    "chatter",
    "notification_logger_listener",
    "notifier",
    "push_channel",
    "sms_channel",
    "tagged_factory",
    "texter",
    "transport_builder",
    "transports",
]


@final
@dataclass(frozen=True, slots=True)
class Kind:
    """One of the two kinds of transports: the chatter's, or the texter's.

    Attributes:
        name: The qualifier its transport builder and its transports are under.
        group: The entry point group its providers are discovered in.
    """

    name: str
    group: str

    @property
    def factory_prefix(self) -> str:
        """What the qualifiers of this kind's tagged factories start with."""
        return f"notifier.{self.name}."


CHATTER: Final = Kind("chatter", TransportFactoryDiscovery.CHATTER_GROUP)
TEXTER: Final = Kind("texter", TransportFactoryDiscovery.TEXTER_GROUP)


def transport_builder(kind: Kind) -> Callable[..., Coroutine[object, object, Transport]]:
    """Return the factory of ``kind``'s transport builder.

    It tries the factories tagged for ``kind`` first, in tag order, then the
    providers discovered in ``kind``'s group — each handed the HTTP client and
    the event dispatcher, when the application has them. Building the factories
    is lazy, so nothing is imported until a DSN of the kind is read.
    """

    async def build(
        factories: ServiceLocator[TransportFactoryInterface],
        http_client: HttpClientPeer,
        event_dispatcher: EventDispatcherPeer,
    ) -> Transport:
        tagged = [
            await factories.get(key)
            for key in factories.provided_services()
            if isinstance(key, str) and key.startswith(kind.factory_prefix)
        ]
        discovery = TransportFactoryDiscovery(
            kind.group,
            http_client=http_client.http_client,
            event_dispatcher=event_dispatcher.event_dispatcher,
        )
        return Transport(tagged, discovery)

    build.__name__ = f"notifier_{kind.name}_transport_builder"
    return build


def tagged_factory(
    factory_class: type[AbstractTransportFactory],
) -> Callable[[HttpClientPeer, EventDispatcherPeer], AbstractTransportFactory]:
    """Return the factory building ``factory_class`` as a discovered one is built.

    A transport factory inheriting its constructor takes the HTTP client and an
    optional event dispatcher — which the container cannot inject as optional —
    so it is handed both from the peers, exactly as discovery would hand them.

    Raises (when built):
        LogicError: If the application has no HTTP client.
    """

    def build(
        http_client: HttpClientPeer, event_dispatcher: EventDispatcherPeer
    ) -> AbstractTransportFactory:
        if http_client.http_client is None:
            raise LogicError(
                f'The "{factory_class.__name__}" transport factory needs an HTTP client; '
                "install xtr-http-client beside xtr-notifier."
            )
        return factory_class(http_client.http_client, event_dispatcher.event_dispatcher)

    build.__name__ = f"notifier_{factory_class.__name__}"
    build.__annotations__ = {
        "http_client": HttpClientPeer,
        "event_dispatcher": EventDispatcherPeer,
        "return": factory_class,
    }
    return build


def transports(kind: Kind) -> Callable[..., Transports]:
    """Return the factory of ``kind``'s named transports, read from the configuration.

    The DSNs are read here, on first use — never at build or boot — so a DSN
    given through ``env()`` is checked where it is used.
    """

    def build(config: NotifierConfig, builder: Transport) -> Transports:
        dsns = config.chatter_transports if kind is CHATTER else config.texter_transports
        return builder.from_strings(dsns)

    build.__name__ = f"notifier_{kind.name}_transports"
    build.__annotations__ = {
        "config": NotifierConfig,
        "builder": Annotated[Transport, Target(kind.name)],
        "return": Transports,
    }
    return build


def chatter(
    transports: Annotated[Transports, Target("chatter")],
    message_bus: Annotated[MessageBusPeer, Target("chat")],
    event_dispatcher: EventDispatcherPeer,
) -> Chatter:
    """Build the chatter, queuing on the bus when chat messages are routed."""
    return Chatter(transports, message_bus.message_bus, event_dispatcher.event_dispatcher)


def texter(
    transports: Annotated[Transports, Target("texter")],
    message_bus: Annotated[MessageBusPeer, Target("texter")],
    event_dispatcher: EventDispatcherPeer,
) -> Texter:
    """Build the texter, queuing on the bus when SMS and push messages are both routed."""
    return Texter(transports, message_bus.message_bus, event_dispatcher.event_dispatcher)


def chat_channel(
    transports: Annotated[Transports, Target("chatter")],
    message_bus: Annotated[MessageBusPeer, Target("chat")],
) -> ChatChannel:
    """Build the ``chat`` channel over the chatter's transports."""
    return ChatChannel(transports, message_bus.message_bus)


def sms_channel(
    transports: Annotated[Transports, Target("texter")],
    message_bus: Annotated[MessageBusPeer, Target("sms")],
) -> SmsChannel:
    """Build the ``sms`` channel over the texter's transports."""
    return SmsChannel(transports, message_bus.message_bus)


def push_channel(
    transports: Annotated[Transports, Target("texter")],
    message_bus: Annotated[MessageBusPeer, Target("push")],
) -> PushChannel:
    """Build the ``push`` channel over the texter's transports."""
    return PushChannel(transports, message_bus.message_bus)


def notifier(config: NotifierConfig, channels: ServiceLocator[ChannelInterface]) -> Notifier:
    """Build the notifier over the channels by name, the policy and the administrators.

    The channels come through a locator, so only those a notification uses are
    built; a policy is set only when one is configured, so a notification
    naming no channel says so rather than meeting an empty policy.
    """
    return Notifier(
        channels,
        ChannelPolicy(config.channel_policy) if config.channel_policy else None,
        [Recipient(admin.email, admin.phone) for admin in config.admin_recipients],
    )


def notification_logger_listener() -> NotificationLoggerListener:
    """Build the listener recording every message event, recording at all times."""
    return NotificationLoggerListener()
