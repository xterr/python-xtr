from __future__ import annotations

import pytest

from xtr_webhook.bundle import NoPrivateNetworkConfig
from xtr_webhook.exception import InvalidArgumentError


def test_the_guard_is_on_by_default() -> None:
    # A webhook URL is the subscriber's to choose: by default none may point inside this network.
    config = NoPrivateNetworkConfig()

    assert config.enabled is True
    assert config.subnets is None
    assert config.allow_list == ()


def test_enabled_with_subnets_and_an_allow_list_builds() -> None:
    config = NoPrivateNetworkConfig(
        enabled=True, subnets=("203.0.113.0/24",), allow_list=("10.1.2.3",)
    )

    assert config.subnets == ("203.0.113.0/24",)
    assert config.allow_list == ("10.1.2.3",)


def test_subnets_without_enabled_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = NoPrivateNetworkConfig(enabled=False, subnets=("10.0.0.0/8",))

    assert str(caught.value) == (
        "no_private_network.subnets and allow_list take effect only with enabled=True."
    )


def test_an_allow_list_without_enabled_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = NoPrivateNetworkConfig(enabled=False, allow_list=("10.1.2.3",))

    assert str(caught.value) == (
        "no_private_network.subnets and allow_list take effect only with enabled=True."
    )


def test_a_subnet_entry_that_is_no_network_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = NoPrivateNetworkConfig(enabled=True, subnets=("nope",))

    assert str(caught.value) == '"nope" is not an IP network.'


def test_an_allow_list_entry_that_is_no_network_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = NoPrivateNetworkConfig(enabled=True, allow_list=("also nope",))

    assert str(caught.value) == '"also nope" is not an IP network.'
