from __future__ import annotations

import pytest

from xtr_webhook.bundle import NoPrivateNetworkConfig, RouteConfig, WebhookConfig
from xtr_webhook.exception import InvalidArgumentError
from xtr_webhook.server import SignatureFormat


def test_the_defaults_mirror_the_senders_and_the_parsers() -> None:
    config = WebhookConfig()

    assert config.http_client is None
    assert config.no_private_network == NoPrivateNetworkConfig()
    assert config.event_header_name == "Webhook-Event"
    assert config.id_header_name == "Webhook-Id"
    assert config.timestamp_header_name == "Webhook-Timestamp"
    assert config.signature_header_name == "Webhook-Signature"
    assert config.signing_algorithm == "sha256"
    assert config.signature_format is SignatureFormat.LEGACY
    assert config.timestamp_tolerance == 300
    assert config.routing == {}


def test_routing_keys_are_kept_verbatim() -> None:
    config = WebhookConfig(routing={"mailer-provider": RouteConfig(secret="the-secret")})

    assert list(config.routing) == ["mailer-provider"]


def test_a_format_string_is_validated_and_kept_as_written() -> None:
    config = WebhookConfig(signature_format="standard")

    assert config.signature_format == "standard"
    assert SignatureFormat.parse(config.signature_format) is SignatureFormat.STANDARD


def test_an_unknown_format_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = WebhookConfig(signature_format="v2")

    assert str(caught.value) == (
        '"v2" is not a signature format; use "legacy", "standard" or "transitional".'
    )


def test_a_negative_timestamp_tolerance_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = WebhookConfig(timestamp_tolerance=-1)

    assert str(caught.value) == "timestamp_tolerance must be greater than or equal to 0."


def test_a_tolerance_of_zero_is_accepted_as_no_bound() -> None:
    assert WebhookConfig(timestamp_tolerance=0).timestamp_tolerance == 0


def test_an_unknown_signing_algorithm_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = WebhookConfig(signing_algorithm="nope")

    assert str(caught.value) == 'The signing algorithm "nope" is not available.'


def test_a_named_client_is_accepted() -> None:
    assert WebhookConfig(http_client="app_client").http_client == "app_client"


def test_a_named_client_can_be_guarded() -> None:
    guard = NoPrivateNetworkConfig(enabled=True)

    config = WebhookConfig(http_client="app_client", no_private_network=guard)

    assert config.no_private_network is guard
