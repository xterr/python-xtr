"""The notifier in prod: ``@when("prod")`` and ``@as_alias`` of the interface."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, as_alias, as_service, when

from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["SmtpNotifier"]


@final
@when("prod")
@as_alias(NotifierInterface)
@as_service
class SmtpNotifier(NotifierInterface):
    """In prod, a mail through the SMTP server ``MAILER_DSN`` names.

    ``MAILER_DSN`` is read when this service is built — never in dev, where the class is
    not even scanned. The sender is a parameter.
    """

    def __init__(
        self,
        mailer: Annotated[dict[str, object], Autowire(env="url:MAILER_DSN")],
        sender: Annotated[str, Autowire(param="shop.support_email")],
    ) -> None:
        """Send through ``mailer`` (the parsed DSN) as ``sender``."""
        self._host = str(mailer["host"])
        self._sender = sender

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        return f"mailed {recipient} from {self._sender} via {self._host}"
