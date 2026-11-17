"""End-to-end: with the http kernel profiling, the mailer panel records what a request sends."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_kernel.profiler import Profiler
from xtr_mime import Email

from xtr_mailer import MailerInterface
from xtr_mailer.bundle import MailerBundle
from xtr_mailer.data_collector import MailerDataCollector

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_PROFILED = ProfiledRequest(
    request=cast("ServerRequestInterface", object()), status_code=200, headers={}, state={}
)


@pytest.fixture(autouse=True)
def _folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(resources: Sequence[str]) -> Kernel:
    return Kernel(
        __name__,
        env="test",
        bundles={MailerBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=tuple(resources),
    )


async def test_the_collector_is_registered_when_the_profiler_is_on() -> None:
    async with await _kernel(["tests.fixtures.profiler_on"]).boot() as booted:
        assert booted.container.has(MailerDataCollector)
        profiler = await booted.container.get(Profiler)

    assert profiler.has("mailer")


async def test_an_email_sent_in_a_profiled_request_is_collected() -> None:
    email = (
        Email()
        .from_("Shop <shop@example.com>")
        .to("customer@example.com")
        .subject("Your order")
        .text("Thanks")
    )
    _ = email.get_headers().add_text_header("X-Api-Key", "key-123")

    async with await _kernel(["tests.fixtures.profiler_on"]).boot() as booted:
        collector = await booted.container.get(MailerDataCollector)
        collector.begin_request()
        await (await booted.container.get(MailerInterface)).send(email)
        data = collector.collect(_PROFILED)
        data = collector.late_collect(data, _PROFILED)

    assert {key: data[key] for key in ("count", "queued", "sent", "failed")} == {
        "count": 1,
        "queued": 0,
        "sent": 1,
        "failed": 0,
    }
    [message] = cast("list[dict[str, object]]", data["messages"])
    assert (message["transport"], message["status"], message["queued"]) == (
        "null://",
        "sent",
        False,
    )
    assert (message["subject"], message["from"], message["to"]) == (
        "Your order",
        ["Shop <shop@example.com>"],
        ["customer@example.com"],
    )
    assert message["text"] == "Thanks"
    headers = cast("dict[str, str]", message["headers"])
    assert headers["X-Api-Key"] == "******"
    assert isinstance(message["message_id"], str)
    assert isinstance(message["size"], int)


async def test_the_collector_is_not_registered_when_the_profiler_is_off() -> None:
    async with await _kernel([]).boot() as booted:
        assert not booted.container.has(MailerDataCollector)
