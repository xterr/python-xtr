from __future__ import annotations

from typing import cast

import pytest

from xtr_mailer.bundle import MailerConfig, TransportConfig
from xtr_mailer.exception import InvalidArgumentError


def test_with_no_dsn_the_one_transport_discards_every_email() -> None:
    assert MailerConfig().get_transports() == {"main": TransportConfig("null://null")}


def test_a_dsn_is_the_main_transport() -> None:
    config = MailerConfig(dsn="smtp://localhost:25")

    assert config.get_transports() == {"main": TransportConfig("smtp://localhost:25")}


def test_named_transports_keep_their_order_and_a_plain_dsn_becomes_a_transport_config() -> None:
    capped = TransportConfig("smtp://b", rate_limiter="mail")
    config = MailerConfig(transports={"a": "smtp://a", "b": capped})

    assert list(config.get_transports().items()) == [
        ("a", TransportConfig("smtp://a")),
        ("b", capped),
    ]


def test_a_dsn_and_named_transports_cannot_be_used_together() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(dsn="smtp://a", transports={"b": "smtp://b"})

    assert str(caught.value) == '"dsn" and "transports" cannot be used together.'


def test_an_empty_dsn_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(dsn="")

    assert str(caught.value) == 'The "dsn" option cannot be empty.'


def test_a_dsn_that_is_not_a_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(dsn=_as_text(["smtp://a"]))

    assert str(caught.value) == 'The "dsn" option must be a string.'


def test_a_transport_that_is_neither_a_dsn_nor_a_transport_config_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(transports={"main": _as_text(25)})

    assert str(caught.value) == 'The "main" transport must be a DSN or a TransportConfig.'


def test_an_empty_transport_dsn_is_refused_without_quoting_it() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(transports={"main": ""})

    assert str(caught.value) == 'The "main" transport\'s DSN cannot be empty.'


def test_an_empty_transport_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(transports={"": "null://null"})

    assert str(caught.value) == "A transport name cannot be empty."


def test_a_header_value_must_be_text_or_a_list_of_text() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MailerConfig(headers={"X-Count": _as_text(3)})

    assert str(caught.value) == 'The "X-Count" header must be a string or a list of strings.'


def test_a_header_may_carry_several_values() -> None:
    config = MailerConfig(headers={"Bcc": ["a@example.com", "b@example.com"], "X-App": "shop"})

    assert config.headers["X-App"] == "shop"


def test_its_repr_never_shows_a_dsn() -> None:
    config = MailerConfig(dsn="smtp://user:s3cr3t@localhost")

    assert "s3cr3t" not in repr(config)


def _as_text(value: object) -> str:
    """Hand ``value`` over where text is expected, as an application's mistake would."""
    return cast("str", value)
