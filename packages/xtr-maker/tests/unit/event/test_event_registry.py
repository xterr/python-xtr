"""Unit tests for :class:`xtr_maker.event.event_registry.EventRegistry`."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, final
from uuid import uuid4

import pytest
from xtr_event_dispatcher import EventDispatcher

from xtr_maker.event import EventRegistry, KnownEvent
from xtr_maker.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_EVENTS = '''"""Two events, a base, and a class that is no event."""

from __future__ import annotations

from abc import ABC, abstractmethod

from xtr_event_dispatcher import Event


class OrderPlaced(Event):
    """Placed."""


class OrderShipped(Event):
    """Shipped."""


class AbstractOrderEvent(Event):
    """Only a base."""


class Refundable(Event, ABC):
    """Abstract."""

    @abstractmethod
    def amount(self) -> int: ...


class NotAnEvent:
    """Plain."""


__all__ = [
    "AbstractOrderEvent",
    "Event",
    "NotAnEvent",
    "OrderPlaced",
    "OrderShipped",
    "Refundable",
]
'''


@final
class _Site:
    """Packages written under a test's temporary directory, importable while it runs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.prefix = f"site_{uuid4().hex}"

    def name(self, package: str) -> str:
        """Return the unique import name of ``package``."""
        return f"{self.prefix}_{package}"

    def write(self, module: str, source: str = '"""A module."""\n') -> None:
        """Write ``module`` — dotted, its first part named by :meth:`name` — and its packages."""
        *packages, last = module.split(".")
        directory = self.root.joinpath(*packages)
        for depth in range(1, len(packages) + 1):
            folder = self.root.joinpath(*packages[:depth])
            folder.mkdir(exist_ok=True)
            init = folder / "__init__.py"
            if not init.exists():
                _ = init.write_text('"""A package."""\n', encoding="utf-8")
        if last == "__init__":
            _ = (directory / "__init__.py").write_text(source, encoding="utf-8")
        else:
            _ = (directory / f"{last}.py").write_text(source, encoding="utf-8")
        importlib.invalidate_caches()


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Site]:
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    written = _Site(tmp_path)
    yield written
    for name in [name for name in sys.modules if name.startswith(written.prefix)]:
        del sys.modules[name]


def _registry(
    site: _Site,
    *packages: str,
    dispatcher: EventDispatcher | None = None,
    root: str = "app",
) -> EventRegistry:
    return EventRegistry(
        dispatcher or EventDispatcher(),
        site.name(root),
        [site.name(package) for package in packages],
    )


def test_the_events_an_event_module_exports_are_listed_under_it(site: _Site) -> None:
    site.write(f"{site.name('shop')}.event.__init__", _EVENTS)

    events = _registry(site, "shop").events()

    module = f"{site.name('shop')}.event"
    assert events == (KnownEvent("OrderPlaced", module), KnownEvent("OrderShipped", module))


def test_the_events_a_package_exports_itself_are_listed_under_it(site: _Site) -> None:
    site.write(f"{site.name('shop')}.__init__", _EVENTS)

    events = _registry(site, "shop").events()

    assert KnownEvent("OrderPlaced", site.name("shop")) in events


def test_an_event_exported_twice_is_listed_once_under_the_event_module(site: _Site) -> None:
    shop = site.name("shop")
    site.write(f"{shop}.event.__init__", _EVENTS)
    site.write(
        f"{shop}.__init__",
        f'"""Re-exports."""\n\nfrom {shop}.event import OrderPlaced\n\n__all__ = ["OrderPlaced"]\n',
    )

    events = _registry(site, "shop").events()

    assert [event for event in events if event.name == "OrderPlaced"] == [
        KnownEvent("OrderPlaced", f"{shop}.event")
    ]


def test_a_package_failing_to_import_or_missing_is_skipped(site: _Site) -> None:
    site.write(f"{site.name('broken')}.__init__", "raise RuntimeError('optional peer missing')\n")
    site.write(f"{site.name('shop')}.event.__init__", _EVENTS)

    events = _registry(site, "broken", "missing", "shop").events()

    assert {event.name for event in events} == {"OrderPlaced", "OrderShipped"}


def test_the_application_events_are_listed_under_the_module_defining_them(site: _Site) -> None:
    app = site.name("app")
    site.write(f"{app}.event.ordering.order_placed", _EVENTS)

    events = _registry(site).events()

    module = f"{app}.event.ordering.order_placed"
    assert events == (KnownEvent("OrderPlaced", module), KnownEvent("OrderShipped", module))


def test_the_dispatcher_events_are_listed_by_class_or_by_name(site: _Site) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener(EventRegistry, print)
    dispatcher.add_listener("order.placed", print)
    dispatcher.add_listener("nowhere.Imported", print)

    events = _registry(site, dispatcher=dispatcher).events()

    assert events == (
        KnownEvent("EventRegistry", "xtr_maker.event.event_registry"),
        KnownEvent("nowhere.Imported"),
        KnownEvent("order.placed"),
    )


def test_labels_name_the_module_and_qualify_a_shared_name(site: _Site) -> None:
    site.write(f"{site.name('shop')}.event.__init__", _EVENTS)
    site.write(f"{site.name('app')}.event.order_placed", _EVENTS)
    dispatcher = EventDispatcher()
    dispatcher.add_listener("order.placed", print)

    labels = _registry(site, "shop", dispatcher=dispatcher).labels()

    assert labels == (
        '"order.placed"',
        f"{site.name('app')}.event.order_placed:OrderPlaced",
        f"{site.name('shop')}.event:OrderPlaced",
        f"{site.name('app')}.event.order_placed:OrderShipped",
        f"{site.name('shop')}.event:OrderShipped",
    )


@pytest.mark.parametrize(
    "typed",
    ["OrderPlaced", " OrderPlaced ", "{shop}.event:OrderPlaced", "{shop}.event.OrderPlaced"],
)
def test_find_resolves_a_name_a_reference_or_a_dotted_path(site: _Site, typed: str) -> None:
    shop = site.name("shop")
    site.write(f"{shop}.event.__init__", _EVENTS)

    found = _registry(site, "shop").find(typed.format(shop=shop))

    assert found == KnownEvent("OrderPlaced", f"{shop}.event")


def test_find_imports_a_class_no_package_lists(site: _Site) -> None:
    module = f"{site.name('other')}.signals"
    site.write(module, '"""A signal."""\n\n\nclass Ping:\n    """Ping."""\n')
    registry = _registry(site)

    assert registry.find(f"{module}:Ping") == KnownEvent("Ping", module)
    assert registry.find(f"{module}.Ping") == KnownEvent("Ping", module)


@pytest.mark.parametrize("typed", ["Nothing", "order.placed", "missing:Thing", "os:path"])
def test_find_returns_none_for_what_names_no_event(site: _Site, typed: str) -> None:
    assert _registry(site).find(typed) is None


def test_find_resolves_an_event_known_by_name(site: _Site) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("order.placed", print)

    assert _registry(site, dispatcher=dispatcher).find("order.placed") == KnownEvent("order.placed")


def test_find_refuses_a_name_shared_by_several_events(site: _Site) -> None:
    site.write(f"{site.name('shop')}.event.__init__", _EVENTS)
    site.write(f"{site.name('app')}.event.order_placed", _EVENTS)

    with pytest.raises(InvalidArgumentError, match="'OrderPlaced' names several events"):
        _ = _registry(site, "shop").find("OrderPlaced")


def test_suggestions_are_the_close_names_the_closest_first(site: _Site) -> None:
    shop = site.name("shop")
    site.write(f"{shop}.event.__init__", _EVENTS)
    registry = _registry(site, "shop")

    assert registry.suggestions("orderplace") == (KnownEvent("OrderPlaced", f"{shop}.event"),)
    assert registry.suggestions(f"{shop}.event:OrderShiped") == (
        KnownEvent("OrderShipped", f"{shop}.event"),
    )
    assert registry.suggestions("OrderPlaxed") == (KnownEvent("OrderPlaced", f"{shop}.event"),)
    assert registry.suggestions("Invoice") == ()


def test_installed_packages_are_the_xtr_distributions_by_import_name() -> None:
    packages = EventRegistry.installed_packages()

    assert {"xtr_maker", "xtr_messenger", "xtr_event_dispatcher"} <= set(packages)
    assert all(package.startswith("xtr_") for package in packages)
    assert list(packages) == sorted(packages)


def test_the_installed_packages_bring_their_events() -> None:
    registry = EventRegistry(EventDispatcher(), "app", EventRegistry.installed_packages())

    assert registry.find("WorkerStartedEvent") == KnownEvent(
        "WorkerStartedEvent", "xtr_messenger.event"
    )
    assert registry.find("PreRunEvent") == KnownEvent("PreRunEvent", "xtr_scheduler.event")
