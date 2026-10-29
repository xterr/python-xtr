"""``make:listener`` in an application: run through its console, then registered by its kernel."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import ExitCode
from xtr_event_dispatcher import EventDispatcherInterface
from xtr_event_dispatcher.bundle import EventDispatcherBundle

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
    from types import MethodType

pytestmark = pytest.mark.anyio

_ORDER_PLACED = '''"""An order was placed."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_event_dispatcher import Event


@dataclass(frozen=True)
class OrderPlaced(Event):
    """An order was placed."""

    number: str
'''

_LONG_EVENT = '''"""An event with a name long enough to split the lines naming it."""

from __future__ import annotations

from xtr_event_dispatcher import Event


class CustomerSubscriptionRenewedEvent(Event):
    """A customer renewed a subscription."""
'''

_GENERATED = (
    "event_listener/send_receipt_listener.py",
    "event_subscriber/sales_tally_subscriber.py",
)

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, and one of each pair of docstring conventions that exclude each other."""


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(
        tmp_path,
        bundles=(EventDispatcherBundle,),
        modules={"event.order_placed": _ORDER_PLACED, "event.long_event": _LONG_EVENT},
    ) as app:
        yield app


async def test_a_listener_and_a_subscriber_run_when_their_event_is_dispatched(
    app: TemporaryApp,
) -> None:
    listened, output = await app.run(["make:listener", "send receipt", "OrderPlaced", "-n"])
    subscribed, more = await app.run(
        ["make:listener"], inputs=["SalesTallySubscriber", "OrderPlaced"]
    )

    assert listened == ExitCode.SUCCESS, output
    assert subscribed == ExitCode.SUCCESS, more
    event_class = cast(
        "Callable[[str], object]", app.import_generated("event.order_placed").OrderPlaced
    )
    _ = app.import_generated("event_listener.send_receipt_listener")
    _ = app.import_generated("event_subscriber.sales_tally_subscriber")
    async with await app.boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        _ = await dispatcher.dispatch(event_class("A-1"))
        ran = dispatcher.get_listeners(cast("type", event_class))

    # A listener is built the first time it runs, and its bound method replaces it then.
    assert sorted(
        f"{type(method.__self__).__name__}.{method.__name__}"
        for method in cast("list[MethodType]", ran)
    ) == [
        "SalesTallySubscriber.on_order_placed",
        "SendReceiptListener.on_order_placed",
    ]


async def test_the_events_of_the_application_and_the_packages_are_offered(
    app: TemporaryApp,
) -> None:
    _, output = await app.run(["make:listener"], inputs=["AuditListener", "OrderPlaced"])

    assert f"* OrderPlaced ({app.package}.event.order_placed)" in output
    assert "* WorkerStartedEvent (xtr_messenger.event)" in output


async def test_an_unknown_event_ends_the_run_as_invalid(app: TemporaryApp) -> None:
    code, output = await app.run(["make:listener", "AuditListener", "OrderPlaces", "-n"])

    assert code == ExitCode.INVALID
    assert "did you mean" in output
    assert f"{app.package}.event.order_placed:OrderPlaced" in output


async def test_the_generated_files_pass_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    long_event = "CustomerSubscriptionRenewedEvent"
    for argv in (
        ["make:listener", "send receipt", "OrderPlaced", "-n"],
        ["make:listener", "SalesTallySubscriber", "OrderPlaced", "-n"],
        ["make:listener", "LongListener", long_event, "-n"],
        ["make:listener", "LongSubscriber", long_event, "-n"],
    ):
        code, output = await app.run(argv)
        assert code == ExitCode.SUCCESS, output
    paths = [
        str(app.package_dir / path)
        for path in (
            *_GENERATED,
            "event_listener/long_listener.py",
            "event_subscriber/long_subscriber.py",
        )
    ]

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, *paths)
    formatted = _ruff(app, "format", "--check", *paths)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


async def test_the_maker_is_listed_with_the_event_dispatcher_bundle(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:listener" in listed


async def test_the_maker_is_not_offered_without_the_event_dispatcher_bundle(
    tmp_path: Path,
) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:listener" not in listed


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
