"""``make:webhook`` in an application: run through its console, then routed by its kernel."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import ExitCode
from xtr_remote_event import ConsumerLocator, RemoteEvent
from xtr_webhook.bundle import WebhookBundle, WebhookConfig
from xtr_webhook.client import RequestParserInterface
from xtr_webhook.exception import RejectWebhookError
from xtr_webhook.testing import ParserCase, assert_parses

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_BASE = '''"""The application's own webhook configuration, which the maker never edits."""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_webhook.bundle import RouteConfig, WebhookConfig


@configure
def webhook() -> WebhookConfig:
    return WebhookConfig(routing={"github": RouteConfig(secret=env("GITHUB_WEBHOOK_SECRET"))})
'''

_GENERATED = (
    "webhook/stripe_request_parser.py",
    "remote_event/stripe_webhook_consumer.py",
    "config/packages/webhook_stripe.py",
)

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, and one of each pair of docstring conventions that exclude each other."""

_SHARED = "s3cret"
_SECRETS = dict.fromkeys(
    ("GITHUB_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET", "ACME_PAY_WEBHOOK_SECRET"), _SHARED
)
"""Set only once the maker has run: making a webhook must not need any secret set."""

_PAYLOAD = b'{"id": "evt_1", "amount": 1200}'


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(
        tmp_path, bundles=(WebhookBundle,), modules={"config.packages.webhook": _BASE}
    ) as app:
        yield app


async def _routing(app: TemporaryApp) -> dict[str, type[RequestParserInterface] | None]:
    app.environ |= _SECRETS
    async with await app.boot() as booted:
        config = await booted.container.get(WebhookConfig)
    return {name: route.parser for name, route in config.routing.items()}


def _parser_class(app: TemporaryApp) -> type[RequestParserInterface]:
    module = app.import_generated("webhook.stripe_request_parser")
    return cast("type[RequestParserInterface]", module.StripeRequestParser)


async def test_answers_write_a_route_added_to_the_applications_own(app: TemporaryApp) -> None:
    code, output = await app.run(["make:webhook"], inputs=["stripe", "Method", "IsJson", ""])

    assert code == ExitCode.SUCCESS, output
    assert await _routing(app) == {"github": None, "stripe": _parser_class(app)}


async def test_the_consumer_is_registered_under_the_webhook_type(app: TemporaryApp) -> None:
    _ = await app.run(["make:webhook", "stripe", "-n"])
    consumer_module = app.import_generated("remote_event.stripe_webhook_consumer")
    consumer = cast("type[object]", consumer_module.StripeWebhookConsumer)
    app.environ |= _SECRETS

    async with await app.boot() as booted:
        locator = await booted.container.get(ConsumerLocator)
        built: object = await booted.container.get(consumer)

    assert locator.provided_services()["stripe"] is consumer
    assert isinstance(built, consumer)


async def test_the_route_applies_without_a_configuration_of_the_applications_own(
    tmp_path: Path,
) -> None:
    with TemporaryApp(tmp_path, bundles=(WebhookBundle,)) as bare:
        code, output = await bare.run(["make:webhook", "stripe", "-n"])

        assert code == ExitCode.SUCCESS, output
        assert await _routing(bare) == {"stripe": _parser_class(bare)}


async def test_two_webhooks_add_two_routes(app: TemporaryApp) -> None:
    _ = await app.run(["make:webhook", "stripe", "-n"])
    code, output = await app.run(["make:webhook", "acme-pay", "-n"])

    assert code == ExitCode.SUCCESS, output
    acme_module = app.import_generated("webhook.acme_pay_request_parser")
    acme = cast("type[RequestParserInterface]", acme_module.AcmePayRequestParser)
    assert await _routing(app) == {
        "github": None,
        "stripe": _parser_class(app),
        "acme-pay": acme,
    }


async def test_a_routed_type_ends_the_run_as_invalid(app: TemporaryApp) -> None:
    code, output = await app.run(["make:webhook", "github", "-n"])

    assert code == ExitCode.INVALID
    assert "The webhook type 'github' is already routed." in output


async def test_an_unknown_matcher_ends_the_run_as_invalid(app: TemporaryApp) -> None:
    code, output = await app.run(["make:webhook", "stripe", "--matcher", "Body", "-n"])

    assert code == ExitCode.INVALID
    assert "There is no request matcher 'Body'" in output


async def test_the_parser_reads_a_webhook_carrying_the_secret(app: TemporaryApp) -> None:
    _ = await app.run(["make:webhook", "stripe", "-n"])
    app.environ |= _SECRETS
    expected = RemoteEvent("stripe", "evt_1", {"id": "evt_1", "amount": 1200})

    async with await app.boot() as booted:
        parser = await booted.container.get(_parser_class(app))

    await assert_parses(
        parser,
        ParserCase("payment.json", _PAYLOAD, expected),
        secret=_SHARED,
        headers={"Stripe-Signature": _SHARED},
    )


async def test_the_parser_refuses_a_webhook_without_the_secret(app: TemporaryApp) -> None:
    _ = await app.run(["make:webhook", "stripe", "-n"])
    parser = _parser_class(app)()
    case = ParserCase("payment.json", _PAYLOAD, RemoteEvent("stripe", "evt_1", {}))

    with pytest.raises(RejectWebhookError, match=r"The signature does not match\."):
        await assert_parses(parser, case, secret=_SHARED, headers={"Stripe-Signature": "forged"})


async def test_the_generated_files_pass_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    _ = await app.run(["make:webhook", "stripe", "--matcher", "Header", "--matcher", "Path", "-n"])
    paths = [str(app.package_dir / path) for path in _GENERATED]

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, *paths)
    formatted = _ruff(app, "format", "--check", *paths)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


async def test_the_maker_is_not_offered_without_the_webhook_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:webhook" not in listed


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
