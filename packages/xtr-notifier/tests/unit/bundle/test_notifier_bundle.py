from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_event_dispatcher.bundle import EventDispatcherBundle

from xtr_notifier import Notifier, NotifierInterface
from xtr_notifier.bundle import NotifierBundle
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.exception import LogicError
from xtr_notifier.notification import Notification

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle

pytestmark = pytest.mark.anyio


def _bare() -> Kernel:
    return Kernel(
        "xtr_notifier.bundle", env="test", bundles={NotifierBundle: {"all": True}}, resources=()
    )


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(NotifierBundle)


async def test_the_logger_listener_is_registered_only_in_debug() -> None:
    # It keeps every message sent, which a long-lived production process must not.
    bundles: Mapping[type[AnyBundle], Mapping[str, bool]] = {
        NotifierBundle: {"all": True},
        EventDispatcherBundle: {"all": True},
    }
    for debug, expected in ((True, True), (False, False)):
        kernel = Kernel(
            "xtr_notifier.bundle", env="prod", debug=debug, bundles=bundles, resources=()
        )
        async with await kernel.boot() as booted:
            assert booted.container.has(NotificationLoggerListener) is expected


async def test_with_no_configuration_the_notifier_has_no_channel_to_send_on() -> None:
    async with await _bare().boot() as booted:
        notifier = await booted.container.get(NotifierInterface)

        with pytest.raises(LogicError) as caught:
            await notifier.send(Notification("Hello", channels=["chat"]))

    assert isinstance(notifier, Notifier)
    assert str(caught.value) == 'The "chat" channel does not exist.'
