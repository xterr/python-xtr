from __future__ import annotations

from xtr_webhook.exception import RejectWebhookError, WebhookError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(RejectWebhookError, WebhookError)


def test_a_rejection_that_names_no_code_is_not_acceptable() -> None:
    assert RejectWebhookError().status_code == 406


def test_it_carries_the_status_code_it_is_given() -> None:
    assert RejectWebhookError(401).status_code == 401


def test_a_rejection_that_names_no_headers_carries_none() -> None:
    assert dict(RejectWebhookError().headers) == {}


def test_it_carries_the_headers_it_is_given() -> None:
    error = RejectWebhookError(401, "no signature", {"WWW-Authenticate": "Signature"})

    assert dict(error.headers) == {"WWW-Authenticate": "Signature"}


def test_it_carries_the_message_it_is_given() -> None:
    assert str(RejectWebhookError(406, "the signature does not match")) == (
        "the signature does not match"
    )


def test_a_rejection_that_names_no_reason_has_no_message() -> None:
    assert str(RejectWebhookError()) == ""
