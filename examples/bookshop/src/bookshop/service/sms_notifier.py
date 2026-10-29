"""A notifier removed because a class it needs cannot be imported."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_service, remove_if_missing

from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["SmsNotifier"]


@final
@remove_if_missing(class_="twilio.rest:Client")
@as_service
class SmsNotifier(NotifierInterface):
    """Removed from the container: ``twilio.rest:Client`` cannot be imported here.

    ``class_=`` is a ``"module:Class"`` path, checked when the container compiles; the
    trailing underscore is because ``class`` is a keyword.
    """

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        return f"texted {recipient}"
