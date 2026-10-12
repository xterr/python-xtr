from __future__ import annotations

from xtr_webhook.exception import DeliveryError, PrivateNetworkError


def test_it_is_a_delivery_that_did_not_happen() -> None:
    assert isinstance(PrivateNetworkError("metadata.test", "169.254.169.254"), DeliveryError)


def test_its_message_names_the_host_and_the_address_it_resolved_to() -> None:
    assert str(PrivateNetworkError("metadata.test", "169.254.169.254")) == (
        'The host "metadata.test" resolves to "169.254.169.254", which is in a private network.'
    )


def test_it_carries_the_host_and_the_address() -> None:
    error = PrivateNetworkError("metadata.test", "169.254.169.254")

    assert error.host == "metadata.test"
    assert error.address == "169.254.169.254"


def test_nothing_answered_so_there_is_no_status_code() -> None:
    assert PrivateNetworkError("metadata.test", "169.254.169.254").status_code == 0
