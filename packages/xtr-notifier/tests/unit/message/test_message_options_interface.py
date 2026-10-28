from __future__ import annotations

from xtr_notifier.message import MessageOptions, MessageOptionsInterface


class _Builder:
    def __init__(self) -> None:
        self._values: dict[str, object] = {"text": "hi"}

    @property
    def recipient_id(self) -> str | None:
        return "ops"

    def to_options(self) -> MessageOptions:
        return MessageOptions("test", self.recipient_id, self._values)


def test_a_builder_rendering_options_is_a_message_options_builder() -> None:
    builder = _Builder()

    assert isinstance(builder, MessageOptionsInterface)
    assert builder.to_options() == MessageOptions("test", "ops", {"text": "hi"})


def test_rendered_options_are_not_a_builder() -> None:
    assert not isinstance(MessageOptions("test"), MessageOptionsInterface)
