"""An HTML-to-text converter: what turns an HTML body into the text a plain-text reader gets."""

from __future__ import annotations

from xtr_mime.html_to_text_converter import (
    DefaultHtmlToTextConverter,
    HtmlToTextConverterInterface,
)


class _Shouting:
    def convert(self, html: str, charset: str) -> str:
        del charset
        return html.upper()


def test_a_class_with_convert_is_a_converter() -> None:
    assert isinstance(_Shouting(), HtmlToTextConverterInterface)


def test_the_default_converter_is_a_converter() -> None:
    assert isinstance(DefaultHtmlToTextConverter(), HtmlToTextConverterInterface)


def test_an_object_without_convert_is_not_a_converter() -> None:
    assert not isinstance(object(), HtmlToTextConverterInterface)
