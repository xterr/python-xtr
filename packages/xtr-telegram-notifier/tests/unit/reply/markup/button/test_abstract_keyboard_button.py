from __future__ import annotations

from xtr_telegram_notifier.reply.markup.button import AbstractKeyboardButton


class _Button(AbstractKeyboardButton):
    def __init__(self) -> None:
        super().__init__()
        self._options["nested"] = {"key": "value"}


def test_it_renders_its_options_as_a_deep_copy() -> None:
    button = _Button()

    array = button.to_array()
    nested = array["nested"]
    assert isinstance(nested, dict)
    nested["key"] = "changed"

    assert button.to_array() == {"nested": {"key": "value"}}
