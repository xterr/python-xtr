from __future__ import annotations

from xtr_mailer.transport.smtp._smtp_session_thresholds import SmtpSessionThresholds


def test_the_thresholds_default_to_a_hundred() -> None:
    thresholds = SmtpSessionThresholds()

    assert (thresholds._restart_threshold, thresholds._restart_threshold_sleep) == (100, 0.0)
    assert thresholds._ping_threshold == 100.0


def test_each_setter_keeps_its_values_and_returns_the_owner() -> None:
    thresholds = SmtpSessionThresholds()

    returned = thresholds.set_restart_threshold(5, 1.5).set_ping_threshold(30)

    assert returned is thresholds
    assert (thresholds._restart_threshold, thresholds._restart_threshold_sleep) == (5, 1.5)
    assert thresholds._ping_threshold == 30
