"""The notifiers, chosen per environment, plus a qualified one and a decorated one.

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

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import (
    Autowire,
    AutowireDecorated,
    Target,
    as_alias,
    as_decorator,
    as_service,
    remove_if_missing,
    when,
    when_not,
)
from xtr_logging_contracts import LoggerInterface

from .notifier_interface import NotifierInterface

__all__ = [
    "LogNotifier",
    "SmsNotifier",
    "SmtpNotifier",
    "UrgentNotifier",
    "ops_notifier",
]


@final
@when_not("prod")
@as_alias(NotifierInterface)
@as_service
class LogNotifier(NotifierInterface):
    """Outside prod, a notification is a log record on the ``orders`` channel."""

    def __init__(self, logger: Annotated[LoggerInterface, Target("orders")]) -> None:
        """Write to ``logger``."""
        self._logger = logger

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        self._logger.notice(
            "to {recipient}: {message}", {"recipient": recipient, "message": message}
        )
        return f"logged for {recipient}"


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


@final
class OpsNotifier(NotifierInterface):
    """Staff notifications, on the ``security`` channel."""

    def __init__(self, logger: LoggerInterface) -> None:
        """Write to ``logger``."""
        self._logger = logger

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        self._logger.warning(
            "ops {recipient}: {message}", {"recipient": recipient, "message": message}
        )
        return f"paged {recipient}"


@as_service(qualifier="ops")
def ops_notifier(logger: Annotated[LoggerInterface, Target("security")]) -> NotifierInterface:
    """A second ``NotifierInterface``, told apart by the qualifier ``"ops"``.

    Asked for with ``Annotated[NotifierInterface, Target("ops")]`` or
    ``container.get(NotifierInterface, "ops")``.
    """
    return OpsNotifier(logger)


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
