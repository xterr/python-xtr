"""What an ESMTP transport is configured with, laid out so two transports compare equal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mailer.transport.smtp import EsmtpTransport

if TYPE_CHECKING:
    from xtr_mailer.transport import TransportInterface

__all__ = ["esmtp_state"]


def esmtp_state(transport: TransportInterface) -> dict[str, object]:
    """Return every setting ``transport`` sends with: two equal states send alike.

    The upstream factory cases compare whole transports; these are the parts of one that
    a DSN sets, plus the collaborators it is built with.
    """
    assert isinstance(transport, EsmtpTransport)
    return {
        "type": type(transport),
        "config": transport._config,
        "username": transport.get_username(),
        "password": transport.get_password(),
        "auto_tls": transport.is_auto_tls(),
        "require_tls": transport.is_tls_required(),
        "restart_threshold": (transport._restart_threshold, transport._restart_threshold_sleep),
        "ping_threshold": transport._ping_threshold,
        "max_per_second": transport._rate,
        "event_dispatcher": transport._event_dispatcher,
        "logger": type(transport._logger),
        "authenticators": [type(authenticator) for authenticator in transport._authenticators],
    }
