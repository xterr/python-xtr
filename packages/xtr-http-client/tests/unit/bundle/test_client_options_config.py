from __future__ import annotations

from xtr_http_client.bundle import ClientOptionsConfig, RetryFailedConfig


def test_with_nothing_set_there_is_no_option() -> None:
    assert ClientOptionsConfig().to_options() == {}


def test_only_the_options_that_are_set_are_handed_on() -> None:
    config = ClientOptionsConfig(
        headers={"Accept": "text/plain"},
        timeout=5.0,
        verify_peer=False,
        retry_failed=RetryFailedConfig(enabled=True),
        rate_limiter="api",
    )

    assert config.to_options() == {
        "headers": {"Accept": "text/plain"},
        "timeout": 5.0,
        "verify_peer": False,
    }


def test_the_passphrase_is_kept_out_of_the_repr() -> None:
    phrase = "s3cret"

    assert phrase not in repr(ClientOptionsConfig(passphrase=phrase))
