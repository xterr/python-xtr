"""Testing what an application emails, and the transport factories a provider library ships.

For an application, the email checks read what a
:class:`~xtr_mailer.event_listener.MessageLoggerListener` recorded, listening to
:class:`~xtr_mailer.event.MessageEvent`::

    events = listener.get_events()

    assert_email_count(events, 1, "null://")
    assert_email_is_not_queued(events.get_events()[0])

What an email says — its headers, its subject, its bodies, its attachments — is checked with
:mod:`xtr_mime.testing`, on the emails ``events.get_messages()`` returns.

For a provider library, :func:`assert_factory_cases` holds its transport factory to what every
factory owes — the schemes it serves, the transport it builds from a DSN, a DSN refused for the
reason it is wrong. The library states its cases in a :class:`FactoryCases`; every case is
checked, and every failure is reported at once.

Nothing here needs a test framework: each check raises :class:`AssertionError`, and the
package itself never imports this module.
"""

from __future__ import annotations

from ._email_assertions import (
    assert_email_count,
    assert_email_is_not_queued,
    assert_email_is_queued,
    assert_queued_email_count,
)
from ._factory_assertions import assert_factory_cases
from .factory_cases import PASSWORD, USER, FactoryCases

__all__ = [
    "PASSWORD",
    "USER",
    "FactoryCases",
    "assert_email_count",
    "assert_email_is_not_queued",
    "assert_email_is_queued",
    "assert_factory_cases",
    "assert_queued_email_count",
]
