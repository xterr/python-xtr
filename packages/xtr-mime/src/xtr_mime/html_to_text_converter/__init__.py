"""Converting the HTML body of a message into the text a plain-text reader gets."""

from __future__ import annotations

from .default_html_to_text_converter import DefaultHtmlToTextConverter
from .html_to_text_converter_interface import HtmlToTextConverterInterface

__all__ = ["DefaultHtmlToTextConverter", "HtmlToTextConverterInterface"]
