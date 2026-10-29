"""A decorator of one qualified service only: ``@as_decorator(..., qualifier="ops")``."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import AutowireDecorated, as_decorator

from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["UrgentNotifier"]


@final
@as_decorator(NotifierInterface, qualifier="ops")
class UrgentNotifier(NotifierInterface):
    """Decorates only the ``"ops"`` notifier: ``qualifier=`` picks which one."""

    def __init__(self, inner: Annotated[NotifierInterface, AutowireDecorated()]) -> None:
        """Wrap ``inner``."""
        self._inner = inner

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        return self._inner.notify(recipient, f"[URGENT] {message}")
