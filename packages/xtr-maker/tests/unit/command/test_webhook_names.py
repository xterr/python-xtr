"""Unit tests for :mod:`xtr_maker.command._webhook_names`."""

from __future__ import annotations

import pytest

from xtr_maker.command._webhook_names import WebhookNames
from xtr_maker.exception import InvalidClassNameError


def test_every_name_derives_from_the_type() -> None:
    names = WebhookNames.create("acme-pay.v2", root_package="app")

    assert (
        names.parser.module,
        names.consumer.module,
        names.transform,
        names.transform_path.as_posix(),
        names.secret,
    ) == (
        "app.webhook.acme_pay_v2_request_parser",
        "app.remote_event.acme_pay_v2_webhook_consumer",
        "webhook_acme_pay_v2",
        "config/packages/webhook_acme_pay_v2.py",
        "ACME_PAY_V2_WEBHOOK_SECRET",
    )


def test_the_type_is_kept_as_typed_for_the_route_and_the_events() -> None:
    names = WebhookNames.create("acme-pay.v2", root_package="app")

    assert names.transform_context()["name_literal"] == '"acme-pay.v2"'


def test_a_type_spelling_no_class_is_refused() -> None:
    with pytest.raises(InvalidClassNameError):
        _ = WebhookNames.create("-.-", root_package="app")
