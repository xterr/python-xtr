"""Email sent through SMTP, sendmail or a provider's API, picked by a DSN.

A mailer hands each email to a transport built from a DSN (``smtp://localhost:25``,
``sendmail://default``, ``failover(smtp://a smtp://b)``) and sends it in-process, or queues it
on a message bus for a worker to send. Listeners on the way override the envelope and headers,
and sign the email with DKIM or S/MIME.
"""

from __future__ import annotations

__all__: list[str] = []
