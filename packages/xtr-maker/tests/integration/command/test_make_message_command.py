"""``make:message`` in an application: run through its console, then discovered by its kernel."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import ExitCode
from xtr_messenger import HandlersLocator
from xtr_messenger.bundle import MessengerBundle

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_TRANSPORTS = '''"""Two transports for the maker to offer."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig


@configure
def messenger() -> MessageBusConfig:
    return MessageBusConfig(
        transports={"async": TransportConfig("in-memory://"), "sync": TransportConfig("sync://")}
    )
'''

_GENERATED = ("message/place_order.py", "message_handler/place_order_handler.py")

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, and one of each pair of docstring conventions that exclude each other."""


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(
        tmp_path,
        bundles=(MessengerBundle,),
        modules={"config.packages.messenger": _TRANSPORTS},
    ) as app:
        yield app


async def test_answers_write_a_handler_the_kernel_discovers(app: TemporaryApp) -> None:
    code, output = await app.run(["make:message"], inputs=["place order", "async", ""])

    assert code == ExitCode.SUCCESS, output
    message = cast("type[object]", app.import_generated("message.place_order").PlaceOrder)
    handler_module = app.import_generated("message_handler.place_order_handler")
    handler = cast("type[object]", handler_module.PlaceOrderHandler)
    async with await app.boot() as booted:
        handlers = await booted.container.get(HandlersLocator)
        built: object = await booted.container.get(handler)

    assert [found.handler for found in handlers.handlers_for(message)] == [handler]
    assert isinstance(built, handler)


async def test_flags_write_the_message_without_a_question(app: TemporaryApp) -> None:
    code, output = await app.run(
        ["make:message", "PlaceOrder", "--transport", "sync", "--wire-name", "shop.order.v1", "-n"]
    )

    assert code == ExitCode.SUCCESS, output
    assert '@as_message(name="shop.order.v1", transport="sync")' in app.read(_GENERATED[0])


async def test_an_unknown_transport_ends_the_run_as_invalid(app: TemporaryApp) -> None:
    code, output = await app.run(["make:message", "PlaceOrder", "--transport", "queue", "-n"])

    assert code == ExitCode.INVALID
    assert "the configured ones are async, sync" in output


async def test_the_generated_files_pass_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    _ = await app.run(["make:message", "place order", "--transport", "async", "-n"])
    paths = [str(app.package_dir / path) for path in _GENERATED]

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, *paths)
    formatted = _ruff(app, "format", "--check", *paths)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


async def test_the_maker_is_listed_with_the_messenger_bundle(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:message" in listed


async def test_the_maker_is_not_offered_without_the_messenger_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:message" not in listed


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
