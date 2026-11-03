"""What the mailer queues an email on a message bus with, and the handler that sends it.

The mailer dispatches a :class:`SendEmailMessage`; :class:`MessageHandler`, registered for it
on the bus, sends it through the transport — in the same process, or in a worker reading the
queue, where it arrives as the classes it left as.
"""

from __future__ import annotations

from .message_handler import MessageHandler
from .send_email_message import SendEmailMessage

__all__ = ["MessageHandler", "SendEmailMessage"]
