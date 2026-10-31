"""A body renderer: what fills in a message's body before it is sent."""

from __future__ import annotations

from xtr_mime import BodyRendererInterface, Email, Message


class _SubjectAsText:
    def render(self, message: Message) -> None:
        if isinstance(message, Email):
            _ = message.text(message.get_subject() or "")


def test_a_class_with_render_is_a_body_renderer() -> None:
    assert isinstance(_SubjectAsText(), BodyRendererInterface)


def test_a_body_renderer_fills_in_the_body() -> None:
    email = Email().subject("Hello")

    _SubjectAsText().render(email)

    assert email.get_text_body() == "Hello"


def test_an_object_without_render_is_not_a_body_renderer() -> None:
    assert not isinstance(object(), BodyRendererInterface)
