"""Reports a message the bus gave up on to the administrators.

Needs xtr-messenger installed (the ``messenger`` extra), which is why it is not
re-exported by :mod:`xtr_notifier.event_listener`: import it from this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_messenger import HandlersFailedError

from xtr_notifier.admin_recipients_provider_interface import AdminRecipientsProviderInterface
from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.notification import Importance, Notification

if TYPE_CHECKING:
    from xtr_messenger.event import WorkerMessageFailedEvent

    from xtr_notifier.notifier_interface import NotifierInterface

__all__ = ["SendFailedMessageToNotifierListener"]


@final
class SendFailedMessageToNotifierListener:
    """Sends a notification when a worker fails a message for good.

    Listen to :class:`~xtr_messenger.event.WorkerMessageFailedEvent` with
    :meth:`on_message_failed`. A message that will be retried is left alone:
    only the last failure is news. A chat, SMS or push message the notifier
    itself queued is left alone too: reporting it would send another one
    through the transport that just failed. The notification names the message
    type and what went wrong — the first failed handler's error, when several
    handlers ran — at high importance, and goes to the notifier's
    administrators, or to nobody in particular when it has none. The traceback
    is attached only with ``include_traceback``: it may hold the failed
    message's own data.
    """

    __slots__ = ("_include_traceback", "_notifier")

    def __init__(self, notifier: NotifierInterface, *, include_traceback: bool = False) -> None:
        """Report failures through ``notifier``, with the traceback when ``include_traceback``."""
        self._notifier = notifier
        self._include_traceback = include_traceback

    async def on_message_failed(self, event: WorkerMessageFailedEvent) -> None:
        """Notify the administrators that ``event``'s message failed, unless it will be retried."""
        if event.will_retry:
            return
        if isinstance(event.envelope.message, (ChatMessage, SmsMessage, PushMessage)):
            return
        error = event.error
        if isinstance(error, HandlersFailedError) and error.errors:
            error = next(iter(error.errors.values()))
        message_type = type(event.envelope.message).__qualname__
        reason = Notification.from_exception(error).subject
        notification = Notification(
            f'A "{message_type}" message has just failed: {reason}.',
            importance=Importance.HIGH,
            exception=error if self._include_traceback else None,
        )
        recipients = (
            self._notifier.admin_recipients
            if isinstance(self._notifier, AdminRecipientsProviderInterface)
            else ()
        )
        await self._notifier.send(notification, *recipients)
