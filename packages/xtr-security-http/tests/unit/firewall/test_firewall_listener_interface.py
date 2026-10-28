"""The firewall listener interface: its shape, and the chain semantics it prescribes.

The chain semantics — skip on a strict ``False``, run on ``None`` and
``True``, stop once a listener answered — are the interface's contract,
pinned here against fakes; the firewall subscriber that runs a real
chain implements the same three rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response
from xtr_http_kernel import RequestEvent

from tests.support.messages import make_message
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


@final
class FakeFirewallListener:
    """A listener that answers ``supports`` with a fixed verdict and records what runs."""

    def __init__(self, *, supports_answer: bool | None, answers: bool = False) -> None:
        self._supports_answer = supports_answer
        self._answers = answers
        self.supports_calls = 0
        self.authenticate_calls = 0

    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Count the ask, and answer the verdict this listener was built with."""
        del request
        self.supports_calls += 1
        return self._supports_answer

    async def authenticate(self, request_event: RequestEvent) -> None:
        """Record the run, and answer the request when this listener was built to."""
        self.authenticate_calls += 1
        if self._answers:
            request_event.set_response(Response())

    @staticmethod
    def get_priority() -> int:
        """Run wherever the fake was placed: the chain's order is not under test here."""
        return 0


async def _run_chain(
    request_event: RequestEvent, listeners: Sequence[FakeFirewallListener]
) -> None:
    """Run ``listeners`` the way the interface prescribes the chain runs them."""
    for listener in listeners:
        if (await listener.supports(request_event.request)) is False:
            continue
        await listener.authenticate(request_event)
        if request_event.response is not None:
            break


def _event() -> RequestEvent:
    return RequestEvent(make_message(), {})


def test_a_listener_satisfies_the_interface() -> None:
    assert isinstance(FakeFirewallListener(supports_answer=None), FirewallListenerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), FirewallListenerInterface)


async def test_a_listener_answering_false_is_skipped() -> None:
    refusing = FakeFirewallListener(supports_answer=False)
    running = FakeFirewallListener(supports_answer=None)

    await _run_chain(_event(), [refusing, running])

    assert refusing.authenticate_calls == 0
    assert running.authenticate_calls == 1


async def test_a_listener_answering_none_or_true_runs() -> None:
    lazy = FakeFirewallListener(supports_answer=None)
    eager = FakeFirewallListener(supports_answer=True)

    await _run_chain(_event(), [lazy, eager])

    assert lazy.authenticate_calls == 1
    assert eager.authenticate_calls == 1


async def test_a_listener_that_answers_stops_the_chain() -> None:
    answering = FakeFirewallListener(supports_answer=None, answers=True)
    after = FakeFirewallListener(supports_answer=None)

    await _run_chain(_event(), [answering, after])

    assert answering.authenticate_calls == 1
    assert after.supports_calls == 0
