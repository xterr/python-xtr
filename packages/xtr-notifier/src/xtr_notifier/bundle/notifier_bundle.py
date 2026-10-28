"""The xtr-notifier bundle: the notifier, its channels and its senders, from one config.

An application listing :class:`NotifierBundle` gets a :class:`~xtr_notifier.NotifierInterface`
whatever it configures. Configuring chat transports adds the ``chat`` channel and a
:class:`~xtr_notifier.ChatterInterface`; SMS and push transports add the ``sms`` and
``push`` channels and a :class:`~xtr_notifier.TexterInterface`. Each kind of transports is
read by a transport builder of its own, over the providers installed for that kind and the
factories tagged for it. Nothing reads a DSN, or reaches a provider, before a message is sent.

The peers are optional: the HTTP client the providers are reached through, the event
dispatcher messages are announced on, and the message bus a routed message is queued on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    named_factory,
    required_bundle,
)

from xtr_notifier.admin_recipients_provider_interface import AdminRecipientsProviderInterface
from xtr_notifier.channel import ChannelInterface, ChatChannel, PushChannel, SmsChannel
from xtr_notifier.chatter import Chatter
from xtr_notifier.chatter_interface import ChatterInterface
from xtr_notifier.event import MessageEvent
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.exception import LogicError
from xtr_notifier.notifier import Notifier
from xtr_notifier.notifier_interface import NotifierInterface
from xtr_notifier.texter import Texter
from xtr_notifier.texter_interface import TexterInterface
from xtr_notifier.transport import TransportFactoryInterface

from ._peer_wiring import build_from_peers, register_peers
from ._services import (
    CHATTER,
    TEXTER,
    Kind,
    chat_channel,
    chatter,
    notification_logger_listener,
    notifier,
    push_channel,
    sms_channel,
    texter,
    transport_builder,
    transports,
)
from .notifier_config import NotifierConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping

__all__ = [
    "CHANNEL_TAG",
    "CHATTER_TRANSPORT_FACTORY_TAG",
    "TEXTER_TRANSPORT_FACTORY_TAG",
    "NotifierBundle",
]

#: Tags a transport factory the chatter's transport builder tries before discovery.
CHATTER_TRANSPORT_FACTORY_TAG: Final = "notifier.chatter_transport_factory"
#: Tags a transport factory the texter's transport builder tries before discovery.
TEXTER_TRANSPORT_FACTORY_TAG: Final = "notifier.texter_transport_factory"
#: Tags a channel the notifier sends on, under the name its ``channel`` attribute gives.
CHANNEL_TAG: Final = "notifier.channel"

_APPLICATION_FACTORY_TAG: Final = "notifier.transport_factory"
"""What autoconfiguration tags every transport factory with: it serves both kinds."""

_CHAT_HANDLER: Final = "xtr_notifier.bundle._chat_message_handler"
_TEXT_HANDLER: Final = "xtr_notifier.bundle._text_message_handler"
_CHANNELS: Final[Mapping[str, tuple[Callable[..., ChannelInterface], type[ChannelInterface]]]] = {
    "chat": (chat_channel, ChatChannel),
    "sms": (sms_channel, SmsChannel),
    "push": (push_channel, PushChannel),
}
"""The built-in channels: the factory of each, and the class it builds."""
_REQUIRED_FOR_FAILURES: Final = {
    "messenger": "xtr-messenger",
    "event_dispatcher": "xtr-event-dispatcher",
}


@final
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle", ignore_on_invalid=True)
@required_bundle("xtr_messenger.bundle:MessengerBundle", ignore_on_invalid=True)
@required_bundle("xtr_http_client.bundle:HttpClientBundle", ignore_on_invalid=True)
@as_bundle("notifier", config=NotifierConfig)
class NotifierBundle(Bundle[NotifierConfig]):
    """Wires the notifier, its channels, its senders and their transports to the container."""

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Have every transport factory the application registers serve both kinds."""
        _ = builder.register_for_autoconfiguration(TransportFactoryInterface).add_tag(
            _APPLICATION_FACTORY_TAG
        )

    @override
    def load_extension(
        self,
        config: NotifierConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the notifier, and the senders and channels of each configured kind.

        Raises:
            LogicError: When failed messages are to be reported without the
                messenger or the event dispatcher bundle active.
        """
        register_peers(config, services, builder)
        _ = services.set(notifier)
        services.alias(NotifierInterface, Notifier)
        services.alias(AdminRecipientsProviderInterface, Notifier)
        messenger = bundle_active(builder, "messenger")
        if config.chatter_transports:
            _register_kind(services, CHATTER)
            _ = services.set(chatter)
            services.alias(ChatterInterface, Chatter)
            _register_channel(services, "chat")
            if messenger:
                services.load(_CHAT_HANDLER)
        if config.texter_transports:
            _register_kind(services, TEXTER)
            _ = services.set(texter)
            services.alias(TexterInterface, Texter)
            _register_channel(services, "sms")
            _register_channel(services, "push")
            if messenger:
                services.load(_TEXT_HANDLER)
        if bundle_active(builder, "event_dispatcher"):
            _register_logger_listener(services)
        if config.notification_on_failed_messages:
            _register_failed_message_listener(services, builder)

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Hand the transport builders their tagged factories, and the notifier its channels.

        A factory tagged for one kind is aliased for that kind alone; one only
        autoconfiguration tagged serves both. A channel tagged
        :data:`CHANNEL_TAG` joins the notifier under its ``channel`` name.
        """
        kinds = {
            CHATTER_TRANSPORT_FACTORY_TAG: CHATTER,
            TEXTER_TRANSPORT_FACTORY_TAG: TEXTER,
        }
        explicit = {key for tag in kinds for key in builder.find_tagged_service_ids(tag)}
        for tag, kind in kinds.items():
            keys = list(builder.find_tagged_service_ids(tag))
            keys += [
                key
                for key in builder.find_tagged_service_ids(_APPLICATION_FACTORY_TAG)
                if key not in explicit
            ]
            for index, (service, qualifier) in enumerate(keys):
                build_from_peers(builder, (service, qualifier))
                builder.set_alias(
                    TransportFactoryInterface,
                    service,
                    alias_qualifier=f"{kind.factory_prefix}{index}",
                    target_qualifier=qualifier,
                )
        for (service, qualifier), tags in builder.find_tagged_service_ids(CHANNEL_TAG).items():
            for attributes in tags:
                builder.set_alias(
                    ChannelInterface,
                    service,
                    alias_qualifier=cast("Hashable", attributes["channel"]),
                    target_qualifier=qualifier,
                )


def _register_kind(services: ServiceConfigurator, kind: Kind) -> None:
    """Register ``kind``'s transport builder and its named transports, under its name."""
    _ = services.set(transport_builder(kind), qualifier=kind.name)
    _ = services.set(
        named_factory(transports(kind), f"notifier_{kind.name}_transports"),
        qualifier=kind.name,
    )


def _register_channel(services: ServiceConfigurator, name: str) -> None:
    """Register the built-in channel ``name`` and offer it to the notifier under that name."""
    factory, channel = _CHANNELS[name]
    _ = services.set(factory, qualifier=name)
    services.alias(ChannelInterface, channel, alias_qualifier=name, target_qualifier=name)


def _register_logger_listener(services: ServiceConfigurator) -> None:
    """Record every message event, for tests and diagnostics, after every other listener."""
    from xtr_event_dispatcher.bundle import LISTENER_TAG  # noqa: PLC0415 -- optional peer

    _ = services.set(notification_logger_listener).add_tag(
        LISTENER_TAG,
        event=MessageEvent,
        method="on_notification",
        priority=NotificationLoggerListener.PRIORITY,
    )


def _register_failed_message_listener(
    services: ServiceConfigurator, builder: ContainerBuilder
) -> None:
    """Report a message the bus gave up on to the administrators.

    Raises:
        LogicError: When the messenger or the event dispatcher bundle is inactive.
    """
    for bundle, distribution in _REQUIRED_FOR_FAILURES.items():
        if not bundle_active(builder, bundle):
            raise LogicError(
                f'"notification_on_failed_messages" needs the "{bundle}" bundle; install '
                f"{distribution} beside xtr-notifier, or turn the option off."
            )
    from xtr_event_dispatcher.bundle import LISTENER_TAG  # noqa: PLC0415 -- optional peer
    from xtr_messenger.event import WorkerMessageFailedEvent  # noqa: PLC0415 -- optional peer

    from ._failed_messages import failed_message_listener  # noqa: PLC0415 -- names the bus

    _ = services.set(failed_message_listener).add_tag(
        LISTENER_TAG, event=WorkerMessageFailedEvent, method="on_message_failed"
    )
