"""Email sent through SMTP, sendmail or a provider's API, picked by a DSN.

A :class:`Mailer` hands each email to a transport built from a DSN (``smtp://localhost:25``,
``sendmail://default``, ``failover(smtp://a smtp://b)``) and sends it in-process, or queues it
on a message bus for a worker to send. Listeners on the way override the envelope and headers,
and sign the email with DKIM or S/MIME.

An :class:`Envelope` is who an email is delivered for and to, apart from its headers;
:class:`SentMessage` is what a transport sent. A :class:`RemoteTemplateEmail` is rendered by
the mail provider from a :class:`RemoteTemplate` it hosts.
:class:`Transport` builds the transport a DSN string describes.
"""

from __future__ import annotations

from .envelope import Envelope
from .exception import (
    HttpTransportError,
    IncompleteDsnError,
    InvalidArgumentError,
    LogicError,
    MailerError,
    MailerRuntimeError,
    TransportError,
    UnexpectedResponseError,
    UnsupportedSchemeError,
)
from .mailer import Mailer
from .mailer_interface import MailerInterface
from .remote_template import RemoteTemplate
from .remote_template_email import RemoteTemplateEmail
from .sent_message import SentMessage
from .transport import Dsn, DsnOption, Transport

__all__ = [
    "Dsn",
    "DsnOption",
    "Envelope",
    "HttpTransportError",
    "IncompleteDsnError",
    "InvalidArgumentError",
    "LogicError",
    "Mailer",
    "MailerError",
    "MailerInterface",
    "MailerRuntimeError",
    "RemoteTemplate",
    "RemoteTemplateEmail",
    "SentMessage",
    "Transport",
    "TransportError",
    "UnexpectedResponseError",
    "UnsupportedSchemeError",
]
