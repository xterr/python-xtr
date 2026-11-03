from __future__ import annotations

import pytest

from xtr_mailer.bundle import EnvelopeConfig
from xtr_mailer.exception import InvalidArgumentError


def test_with_no_configuration_nothing_is_overridden() -> None:
    config = EnvelopeConfig()

    assert config.is_configured() is False


@pytest.mark.parametrize(
    "config",
    [EnvelopeConfig(sender="bounces@example.com"), EnvelopeConfig(recipients=["qa@example.com"])],
)
def test_a_sender_or_recipients_override_the_envelope(config: EnvelopeConfig) -> None:
    assert config.is_configured() is True


def test_recipients_given_as_one_string_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EnvelopeConfig(recipients="qa@example.com")

    assert str(caught.value) == (
        'The envelope "recipients" option must be a list of addresses, not one string.'
    )


def test_allowed_recipients_given_as_one_string_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EnvelopeConfig(recipients=["qa@example.com"], allowed_recipients=r".*@example\.com")

    assert str(caught.value) == (
        'The envelope "allowed_recipients" option must be a list of patterns, not one string.'
    )


def test_an_allowed_recipient_pattern_that_does_not_compile_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EnvelopeConfig(recipients=["qa@example.com"], allowed_recipients=["(unclosed"])

    assert str(caught.value) == (
        'The allowed recipient pattern "(unclosed" is not a valid regular expression.'
    )
