from __future__ import annotations

import pytest

from xtr_ai.bundle import PlatformConfig
from xtr_ai.exception import InvalidConfigurationError


def test_a_platform_needs_a_provider() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = PlatformConfig(provider="")


def test_a_platforms_key_is_never_shown() -> None:
    assert "sk-secret" not in repr(PlatformConfig(provider="openai", api_key="sk-secret"))


def test_repr_masks_secrets() -> None:
    # Options carry provider credentials under any name, and a base URL may carry userinfo.
    config = PlatformConfig(
        provider="azure",
        base_url="https://user:pw-secret@proxy.example/v1",
        options={"azure_ad_token": "tok-secret", "api_version": "2024-01-01"},
    )

    shown = repr(config)

    assert "pw-secret" not in shown
    assert "tok-secret" not in shown
    assert "2024-01-01" not in shown
    assert "proxy.example" in shown
    assert "azure_ad_token" in shown
