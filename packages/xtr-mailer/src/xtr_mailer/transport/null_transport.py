"""A transport that sends nothing anywhere."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .abstract_transport import AbstractTransport
from .remote_template_transport_interface import RemoteTemplateTransportInterface

if TYPE_CHECKING:
    from xtr_mailer.sent_message import SentMessage

__all__ = ["NullTransport"]


@final
class NullTransport(AbstractTransport, RemoteTemplateTransportInterface):
    """Reports every email sent and sends it nowhere: ``null://null``.

    For an environment that must not reach a mail server — a test run, a local machine — while
    everything up to the send still happens: the email is rendered and the events are
    dispatched, so a listener sees what would have gone out. It takes an email rendered from a
    provider's template too, which no server is there to refuse.
    """

    @override
    async def _do_send(self, message: SentMessage) -> None:
        """Send nothing."""

    @override
    def __str__(self) -> str:
        """Name it ``null://``."""
        return "null://"
