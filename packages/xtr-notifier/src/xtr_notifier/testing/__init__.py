"""Testing what an application notifies, and the transports a provider library ships.

For an application, the ``assert_notification_*`` checks read what a
:class:`~xtr_notifier.event_listener.NotificationLoggerListener` recorded::

    assert_notification_count(listener.events, 1, "slack")
    assert_notification_subject_contains(listener.events.get_messages()[0], "Disk")

For a provider library, :func:`assert_transport_cases` and
:func:`assert_factory_cases` hold its transport and its factory to what every
provider owes — a string form without credentials, the messages it sends, a
refusal of the others, a host and port that can be overridden, a DSN refused
for the reason it is wrong. The library states its cases in a
:class:`TransportCases` and a :class:`FactoryCases`; every case is checked,
and every failure is reported at once.

Nothing here needs a test framework: each check raises :class:`AssertionError`.
"""

from __future__ import annotations

from ._factory_assertions import assert_factory_cases
from ._notification_assertions import (
    assert_notification_count,
    assert_notification_is_not_queued,
    assert_notification_is_queued,
    assert_notification_subject_contains,
    assert_notification_subject_not_contains,
    assert_notification_transport_is,
    assert_notification_transport_is_not,
    assert_queued_notification_count,
)
from ._transport_assertions import CUSTOM_HOST, CUSTOM_PORT, assert_transport_cases
from .factory_cases import FactoryCases
from .transport_cases import TransportCases

__all__ = [
    "CUSTOM_HOST",
    "CUSTOM_PORT",
    "FactoryCases",
    "TransportCases",
    "assert_factory_cases",
    "assert_notification_count",
    "assert_notification_is_not_queued",
    "assert_notification_is_queued",
    "assert_notification_subject_contains",
    "assert_notification_subject_not_contains",
    "assert_notification_transport_is",
    "assert_notification_transport_is_not",
    "assert_queued_notification_count",
    "assert_transport_cases",
]
