from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import pytest
import xtr_messenger.message_registry
from xtr_messenger import MessageBusConfig, TransportConfig, name_of

from xtr_mailer.bundle._message_bus import routed
from xtr_mailer.messenger import SendEmailMessage

if TYPE_CHECKING:
    from collections.abc import Sequence

_TRANSPORTS = {"mail": TransportConfig("in-memory://")}


class _Unchecked(Protocol):
    """A protocol no class can be checked against."""

    def written(self) -> object: ...


@runtime_checkable
class _Writing(Protocol):
    """A protocol a queued email matches by its shape alone."""

    def written(self) -> object: ...


def _routing(key: object, transports: str | Sequence[str] = "mail") -> MessageBusConfig:
    return MessageBusConfig(transports=_TRANSPORTS, routing={cast("type | str", key): transports})


@pytest.mark.parametrize("key", [SendEmailMessage, object, "*"], ids=str)
def test_an_email_the_routing_names_is_queued(key: type | str) -> None:
    assert routed(_routing(key))


@pytest.mark.parametrize(
    "key",
    [name_of(SendEmailMessage), "other", _Writing, _Unchecked, list[int]],
    ids=["wire name", "other name", "matching protocol", "unchecked protocol", "not a class"],
)
def test_an_email_the_routing_does_not_name_is_sent_at_once(key: object) -> None:
    assert not routed(_routing(key))


def test_an_email_routed_to_no_transport_is_sent_at_once() -> None:
    assert not routed(_routing(SendEmailMessage, []))


def test_an_email_whose_class_declares_its_transport_is_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = xtr_messenger.message_registry._TRANSPORTS_BY_TYPE
    monkeypatch.setitem(declared, SendEmailMessage, ("mail",))

    assert routed(MessageBusConfig(transports=_TRANSPORTS))


def test_an_email_handled_unrouted_is_queued() -> None:
    assert routed(MessageBusConfig(handle_unrouted=True))
