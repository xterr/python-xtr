from __future__ import annotations

from xtr_telegram_notifier.reply.markup import AbstractTelegramReplyMarkup


class _Markup(AbstractTelegramReplyMarkup):
    def __init__(self) -> None:
        super().__init__()
        self._options["nested"] = {"key": "value"}


def test_it_renders_its_options_as_a_deep_copy() -> None:
    markup = _Markup()

    array = markup.to_array()
    nested = array["nested"]
    assert isinstance(nested, dict)
    nested["key"] = "changed"

    assert markup.to_array() == {"nested": {"key": "value"}}
