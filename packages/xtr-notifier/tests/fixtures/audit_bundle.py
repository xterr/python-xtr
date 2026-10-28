"""An add-on bundle: a channel of its own, and a provider for the chatter alone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, ContainerBuilder, ServiceConfigurator, as_bundle

# Read at runtime: the container builds the factory from its constructor's annotations.
from xtr_http_client_contracts import HttpClientInterface  # noqa: TC002

from xtr_notifier.bundle import CHANNEL_TAG, CHATTER_TRANSPORT_FACTORY_TAG
from xtr_notifier.channel import ChannelInterface
from xtr_notifier.transport import AbstractTransportFactory, NullTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface
    from xtr_notifier.transport import Dsn

__all__ = ["AUDITED", "AuditBundle", "AuditChannel", "ChatOnlyTransportFactory"]

AUDITED: Final[list[str]] = []
"""The subject of every notification the audit channel was handed."""


@final
class AuditChannel(ChannelInterface):
    """Records each notification's subject."""

    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        AUDITED.append(notification.subject)

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        return True


@final
class ChatOnlyTransportFactory(AbstractTransportFactory):
    """Serves ``chat-only://``, with a constructor of its own the container fills."""

    def __init__(self, http_client: HttpClientInterface) -> None:
        super().__init__(http_client)

    @override
    def create(self, dsn: Dsn) -> NullTransport:
        return NullTransport()

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("chat-only",)


@final
@as_bundle("audit")
class AuditBundle(Bundle):
    """Registers the audit channel and the chat-only provider, through the notifier's tags."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(AuditChannel).add_tag(CHANNEL_TAG, channel="audit")
        _ = services.set(ChatOnlyTransportFactory).add_tag(CHATTER_TRANSPORT_FACTORY_TAG)
