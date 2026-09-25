"""A handler whose output format can be replaced."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_logging.formatter.formatter_interface import FormatterInterface

__all__ = ["FormattableHandlerInterface"]


@runtime_checkable
class FormattableHandlerInterface(Protocol):
    """Renders records through a formatter that can be swapped."""

    @property
    def formatter(self) -> FormatterInterface:
        """The formatter in use; a handler supplies its own default."""
        ...

    @formatter.setter
    def formatter(self, formatter: FormatterInterface, /) -> None: ...
