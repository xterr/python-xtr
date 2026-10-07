"""A user that can report whether its account may authenticate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["EnabledAwareInterface"]


@runtime_checkable
class EnabledAwareInterface(Protocol):
    """A user that answers whether its account is enabled.

    A checker reads this to turn away a disabled account before its credentials
    are ever checked. A user without the method is left alone: the structural
    check simply does not match it, so no assumption is made either way.
    """

    def is_enabled(self) -> bool:
        """Tell whether this account may authenticate."""
        ...
