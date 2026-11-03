from __future__ import annotations

import pytest
from xtr_dependency_injection import ContainerBuilder, bundle_active

from tests.support.mailer_kernel import Application, mailer_kernel
from xtr_mailer.bundle import EnvelopeConfig, MailerConfig, TrackingConfig
from xtr_mailer.bundle import _listeners as listeners_module
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.exception import LogicError

pytestmark = pytest.mark.anyio


@pytest.fixture
def _no_event_dispatcher(monkeypatch: pytest.MonkeyPatch) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        return name != "event_dispatcher" and bundle_active(builder, name)

    monkeypatch.setattr(listeners_module, "bundle_active", active)


@pytest.mark.usefixtures("_no_event_dispatcher")
@pytest.mark.parametrize(
    ("config", "option"),
    [
        (MailerConfig(envelope=EnvelopeConfig(sender="bounces@example.com")), "envelope"),
        (MailerConfig(headers={"X-App": "shop"}), "headers"),
        (MailerConfig(tracking=TrackingConfig(clicks=False)), "tracking"),
    ],
)
def test_an_option_a_listener_carries_out_needs_the_event_dispatcher(
    config: MailerConfig, option: str
) -> None:
    with pytest.raises(LogicError) as caught:
        _ = mailer_kernel(Application(mailer=config)).build()

    assert str(caught.value) == (
        f'The "{option}" option needs the "event_dispatcher" bundle; install '
        "xtr-event-dispatcher beside xtr-mailer."
    )


@pytest.mark.usefixtures("_no_event_dispatcher")
async def test_without_the_event_dispatcher_no_listener_is_registered() -> None:
    async with await mailer_kernel().boot() as booted:
        assert not booted.container.has(MessageLoggerListener)
