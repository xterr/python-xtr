"""The notifier panel through a real kernel: there with the profiler on, absent with it off."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import DataCollectorTemplates, ProfiledRequest
from xtr_http_kernel.profiler import Profiler

from tests.fixtures.app_notifier.factories import SENT
from xtr_notifier import ChatterInterface, TexterInterface
from xtr_notifier.bundle import NotifierBundle
from xtr_notifier.data_collector import NotifierDataCollector
from xtr_notifier.message import ChatMessage, SmsMessage

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.app_notifier"
_PROFILED = ProfiledRequest(
    request=cast("ServerRequestInterface", object()), status_code=200, headers={}, state={}
)


@pytest.fixture(autouse=True)
def _folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))
    SENT.clear()


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        _APP,
        env="test",
        bundles={NotifierBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=(_APP, *resources),
        environ={"FAKE_CHAT_DSN": "fake://ops"},
    )


async def test_the_collector_joins_the_profiler_when_profiling_is_on() -> None:
    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        profiler = await booted.container.get(Profiler)
        templates = await booted.container.get(DataCollectorTemplates)

    assert profiler.has("notifier")
    assert templates.template_of("notifier") == "@xtr_notifier/collector/notifier.html.j2"


async def test_a_profiled_request_s_messages_are_collected() -> None:
    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        collector = await booted.container.get(NotifierDataCollector)
        chatter = await booted.container.get(ChatterInterface)
        texter = await booted.container.get(TexterInterface)
        collector.begin_request()

        _ = await chatter.send(ChatMessage("Deployed", transport="fake"))
        _ = await chatter.send(ChatMessage("Retried", transport="failover"))
        _ = await texter.send(SmsMessage("+3312345678", "Your code is 4812"))

        data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    messages = cast("list[dict[str, object]]", data["messages"])
    assert [
        (message["subject"], message["status"], message["sent_through"]) for message in messages
    ] == [
        ("Deployed", "sent", "fake://ops"),
        ("Retried", "failed", None),
        ("Retried", "sent", "fake://backup"),
        ("Your code is 4812", "queued", None),
        ("Your code is 4812", "sent", "fake://texts"),
    ]
    assert messages[1]["error"] == "TransportError: down"
    assert messages[3]["channel"] == "sms"
    assert messages[3]["recipient"] == "+3312345678"
    assert {key: value for key, value in data.items() if key != "messages"} == {
        "count": 5,
        "queued": 1,
        "sent": 3,
        "failed": 1,
        "by_transport": {"fake": 1, "failover": 2},
    }


async def test_the_collector_is_not_registered_when_profiling_is_off() -> None:
    async with await _kernel().boot() as booted:
        registered = booted.container.has(NotifierDataCollector)

    assert not registered
