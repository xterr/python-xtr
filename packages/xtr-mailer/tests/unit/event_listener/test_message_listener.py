"""The listener adding default headers to every email, and rendering its body."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, Group, Message, RawMessage
from xtr_mime.header import Headers, MailboxListHeader, UnstructuredHeader

from xtr_mailer import Envelope, InvalidArgumentError, MailerRuntimeError
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import MessageListener

if TYPE_CHECKING:
    from collections.abc import Mapping


def _event(message: RawMessage) -> MessageEvent:
    envelope = Envelope(Address("sender@example.com"), [Address("recipient@example.com")])
    return MessageEvent(message, envelope, "smtp")


def _shown(headers: Headers) -> list[tuple[type, str]]:
    return [(type(header), header.to_string()) for header in headers.all()]


def _text(*pairs: tuple[str, str]) -> Headers:
    return Headers(*(UnstructuredHeader(name, value) for name, value in pairs))


def _bcc(*entries: Address | Group) -> Headers:
    return Headers(MailboxListHeader("bcc", entries))


_DEFAULTS = _text(("foo", "bar"), ("bar", "foo"))


@pytest.mark.parametrize(
    ("initial", "defaults", "expected", "rules"),
    [
        pytest.param(
            Headers(),
            Headers(MailboxListHeader("from", [Address("from-default@example.com")])),
            Headers(MailboxListHeader("from", [Address("from-default@example.com")])),
            MessageListener.DEFAULT_RULES,
            id="no defaults, all headers copied over",
        ),
        pytest.param(
            Headers(),
            _DEFAULTS,
            _DEFAULTS,
            MessageListener.DEFAULT_RULES,
            id="no defaults, default is to set if empty",
        ),
        pytest.param(
            _text(("foo", "initial")),
            _DEFAULTS,
            _text(("foo", "initial"), ("bar", "foo")),
            MessageListener.DEFAULT_RULES,
            id="some defaults, default is to set if empty",
        ),
        pytest.param(
            _text(("foo", "initial")),
            _DEFAULTS,
            _DEFAULTS,
            {"foo": MessageListener.HEADER_REPLACE},
            id="some defaults, replace if set",
        ),
        pytest.param(
            _text(("foo", "bar")),
            _text(("foo", "foo")),
            _text(("foo", "bar"), ("foo", "foo")),
            {"foo": MessageListener.HEADER_ADD},
            id="some defaults, add if set (not unique header)",
        ),
        pytest.param(
            _bcc(Address("bcc-initial@example.com")),
            _bcc(Address("bcc-default@example.com"), Address("bcc-default-1@example.com")),
            _bcc(
                Address("bcc-initial@example.com"),
                Address("bcc-default@example.com"),
                Address("bcc-default-1@example.com"),
            ),
            MessageListener.DEFAULT_RULES,
            id="bcc, add another bcc (unique header)",
        ),
        pytest.param(
            _bcc(Address("bcc-initial@example.com")),
            _bcc(Group("Watchers", [Address("bcc-default@example.com")])),
            _bcc(
                Address("bcc-initial@example.com"),
                Group("Watchers", [Address("bcc-default@example.com")]),
            ),
            MessageListener.DEFAULT_RULES,
            id="bcc, add a bcc holding a group (unique header)",
        ),
        pytest.param(
            _text(("foo", "initial")),
            _DEFAULTS,
            _DEFAULTS,
            {"Foo": MessageListener.HEADER_REPLACE},
            id="capitalized header rule (case-insensitive), replace if set",
        ),
    ],
)
def test_headers(
    initial: Headers, defaults: Headers, expected: Headers, rules: Mapping[str, int]
) -> None:
    listener = MessageListener(defaults, None, rules)
    event = _event(Message(initial))

    listener.on_message(event)

    message = event.get_message()
    assert isinstance(message, Message)
    assert _shown(message.get_headers()) == _shown(expected)


def test_it_runs_at_the_default_priority() -> None:
    assert MessageListener.PRIORITY == 0


def test_the_default_rules_add_to_the_lists_and_set_the_rest_if_empty() -> None:
    assert MessageListener.DEFAULT_RULES == {
        "from": MessageListener.HEADER_SET_IF_EMPTY,
        "return-path": MessageListener.HEADER_SET_IF_EMPTY,
        "reply-to": MessageListener.HEADER_ADD,
        "to": MessageListener.HEADER_SET_IF_EMPTY,
        "cc": MessageListener.HEADER_ADD,
        "bcc": MessageListener.HEADER_ADD,
    }


@pytest.mark.parametrize("rule", [0, 4])
def test_a_rule_that_does_not_exist_is_refused(rule: int) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = MessageListener(header_rules={"foo": rule})

    assert str(caught.value) == f'The "{rule}" rule is not supported.'


def test_a_rule_is_added_after_construction() -> None:
    listener = MessageListener(_text(("foo", "bar")))
    listener.add_header_rule("FOO", MessageListener.HEADER_REPLACE)
    event = _event(Message(_text(("foo", "initial"))))

    listener.on_message(event)

    message = event.get_message()
    assert isinstance(message, Message)
    assert message.get_headers().get_header_body("foo") == "bar"


def test_adding_to_a_unique_header_that_is_not_an_address_list_is_refused() -> None:
    listener = MessageListener(_text(("Subject", "Default")), None, {"subject": 2})
    event = _event(Message(_text(("Subject", "Initial"))))

    with pytest.raises(MailerRuntimeError) as caught:
        listener.on_message(event)

    assert str(caught.value) == 'Unable to set header "subject".'


def test_a_default_header_added_to_one_email_is_not_shared_with_the_next() -> None:
    listener = MessageListener(_bcc(Address("default@example.com")))
    first, second = Message(), Message()
    listener.on_message(_event(first))
    first_bcc = first.get_headers().get("bcc")
    assert isinstance(first_bcc, MailboxListHeader)

    first_bcc.add_address(Address("first-only@example.com"))
    listener.on_message(_event(second))

    assert second.get_headers().get_header_body("bcc") == [Address("default@example.com")]


def test_the_default_headers_given_are_copied() -> None:
    defaults = _text(("foo", "bar"))
    listener = MessageListener(defaults)
    _ = defaults.add_text_header("bar", "late")
    message = Message()

    listener.on_message(_event(message))

    assert _shown(message.get_headers()) == _shown(_text(("foo", "bar")))


class _Renderer:
    def __init__(self) -> None:
        self.rendered: list[Message] = []

    def render(self, message: Message) -> None:
        self.rendered.append(message)


def test_the_renderer_renders_the_email_after_its_headers_are_set() -> None:
    renderer = _Renderer()
    message = Message()

    MessageListener(_text(("foo", "bar")), renderer).on_message(_event(message))

    assert renderer.rendered == [message]
    assert message.get_headers().has("foo")


def test_without_headers_or_renderer_the_email_is_left_as_it_is() -> None:
    message = Message(_text(("foo", "initial")))
    before = _shown(message.get_headers())

    MessageListener().on_message(_event(message))

    assert _shown(message.get_headers()) == before


def test_raw_bytes_are_left_as_they_are() -> None:
    renderer, raw = _Renderer(), RawMessage("raw")
    event = _event(raw)

    MessageListener(_text(("foo", "bar")), renderer).on_message(event)

    assert event.get_message() is raw
    assert renderer.rendered == []
