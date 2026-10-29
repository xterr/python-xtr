"""What sends a message to someone — and which notifier provides it where.

========================  ================================  =================================
Key                       Provided by                       Where
========================  ================================  =================================
``NotifierInterface``     ``LogNotifier`` (alias)           every environment but prod
``NotifierInterface``     ``SmtpNotifier`` (alias)          prod only
``(Notifier…, "ops")``    ``ops_notifier`` factory          everywhere, wrapped by
                                                            ``UrgentNotifier``
``SmsNotifier``           ``@remove_if_missing(class_=…)``  nowhere: its SDK is not installed
========================  ================================  =================================

``@when`` / ``@when_not`` leave an object out of the scan for other environments, as if it
did not exist — the scan report (``debug:container``'s scan section) says why. ``@as_alias``
is unconditional: gate the class, not the alias.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["NotifierInterface"]


@runtime_checkable
class NotifierInterface(Protocol):
    """Delivers ``message`` to ``recipient`` and says how."""

    def notify(self, recipient: str, message: str, /) -> str:
        """Deliver, and return a short description of the delivery."""
        ...
