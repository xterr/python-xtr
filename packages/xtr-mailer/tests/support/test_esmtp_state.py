from __future__ import annotations

import pytest

from tests.support.esmtp_state import esmtp_state
from xtr_mailer.transport import NullTransport
from xtr_mailer.transport.smtp import EsmtpTransport


def test_two_transports_built_alike_have_one_state() -> None:
    assert esmtp_state(EsmtpTransport("a").set_timeout(5)) == esmtp_state(
        EsmtpTransport("a").set_timeout(5)
    )


@pytest.mark.parametrize(
    "transport",
    [
        EsmtpTransport("b"),
        EsmtpTransport("a", 25),
        EsmtpTransport("a").set_password("p"),
        EsmtpTransport("a").set_ping_threshold(1),
        EsmtpTransport("a").set_restart_threshold(100, 1),
        EsmtpTransport("a").set_max_per_second(1),
        EsmtpTransport("a").set_require_tls(True),
        EsmtpTransport("a", authenticators=[]),
    ],
)
def test_a_transport_set_differently_has_another_state(transport: EsmtpTransport) -> None:
    assert esmtp_state(transport) != esmtp_state(EsmtpTransport("a"))


def test_another_transport_has_no_state() -> None:
    with pytest.raises(AssertionError):
        _ = esmtp_state(NullTransport())
