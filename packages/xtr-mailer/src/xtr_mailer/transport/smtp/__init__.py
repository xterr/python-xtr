"""Sending email over SMTP, to a mail server or to a local sendmail.

:class:`SmtpTransport` keeps one session with a server and sends each email on it;
:class:`EsmtpTransport` adds the extensions a modern server offers — ``STARTTLS``, ``AUTH``
with the mechanisms of :mod:`xtr_mailer.transport.smtp.auth`, ``SMTPUTF8``.
"""

from __future__ import annotations

from .esmtp_transport import EsmtpTransport
from .smtp_transport import SmtpTransport

__all__ = ["EsmtpTransport", "SmtpTransport"]
