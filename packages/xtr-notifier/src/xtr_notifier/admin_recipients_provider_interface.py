"""Who to tell when something goes wrong."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.recipient import RecipientInterface

__all__ = ["AdminRecipientsProviderInterface"]


@runtime_checkable
class AdminRecipientsProviderInterface(Protocol):
    """Names the administrators of the application, to send its own failures to.

    A failed queued message, for one, is reported to them; a notifier without
    administrators reports it to nobody in particular.
    """

    @property
    def admin_recipients(self) -> Sequence[RecipientInterface]:
        """The administrators, in the order they were configured."""
        ...
