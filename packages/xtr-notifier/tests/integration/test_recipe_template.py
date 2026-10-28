"""The configuration the recipe writes boots, and notifies on every channel it brings."""

from __future__ import annotations

import sys
from importlib.resources import files
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel

from xtr_notifier import NotifierInterface
from xtr_notifier.bundle import NotifierBundle
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.notification import Notification
from xtr_notifier.recipient import Recipient

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_ENVIRON = {"NOTIFIER_CHATTER_DSN": "null://null", "NOTIFIER_TEXTER_DSN": "null://null"}


async def test_the_written_configuration_notifies_through_the_default_dsns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = files("xtr_notifier").joinpath("recipe/files/config/notifier.py.tmpl")
    application = tmp_path / "recipe_app"
    (application / "config").mkdir(parents=True)
    _ = (application / "__init__.py").write_text("", encoding="utf-8")
    _ = (application / "config" / "__init__.py").write_text("", encoding="utf-8")
    _ = (application / "config" / "notifier.py").write_text(template.read_text(), encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    kernel = Kernel(
        "recipe_app", env="test", bundles={NotifierBundle: {"all": True}}, environ=_ENVIRON
    )

    async with await kernel.boot() as booted:
        notifier = await booted.container.get(NotifierInterface)
        await notifier.send(
            Notification("Hi", channels=["chat", "sms", "push"]), Recipient(phone="+33")
        )
        listener = await booted.container.get(NotificationLoggerListener)

    assert listener.events.transports == [""]
    assert len(listener.events.get_events()) == 3
