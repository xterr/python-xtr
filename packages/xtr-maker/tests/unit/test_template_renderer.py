"""Unit tests for :class:`xtr_maker.TemplateRenderer`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from tests.conftest import FIXTURES
from xtr_maker import GeneratedSourceError, MakerError, TemplateRenderer

if TYPE_CHECKING:
    from pathlib import Path

_TEMPLATES = FIXTURES / "templates"


def test_a_template_renders_with_blocks_trimmed_and_its_trailing_newline_kept() -> None:
    renderer = TemplateRenderer((_TEMPLATES,))

    assert renderer.render("greeting.txt.jinja", {"name": "Ada", "loud": False}) == "Hello Ada.\n"


def test_nothing_is_escaped() -> None:
    renderer = TemplateRenderer((_TEMPLATES,))

    assert renderer.render("greeting.txt.jinja", {"name": "<b>", "loud": False}) == "Hello <b>.\n"


def test_python_source_that_parses_is_returned() -> None:
    renderer = TemplateRenderer((_TEMPLATES,))

    assert (
        renderer.render("function.py.jinja", {"name": "go"})
        == "def go() -> None:\n    return None\n"
    )


def test_python_source_that_does_not_parse_is_refused_naming_the_template() -> None:
    renderer = TemplateRenderer((_TEMPLATES,))

    with pytest.raises(GeneratedSourceError) as raised:
        _ = renderer.render("function.py.jinja", {"name": "not valid"})

    assert raised.value.template == "function.py.jinja"
    assert raised.value.line == 1
    assert isinstance(raised.value, MakerError)


def test_a_value_the_template_reads_but_was_not_given_is_an_error() -> None:
    renderer = TemplateRenderer((_TEMPLATES,))

    with pytest.raises(UndefinedError):
        _ = renderer.render("greeting.txt.jinja", {"loud": False})


def test_a_directory_listed_first_replaces_a_template_of_the_same_name(tmp_path: Path) -> None:
    _ = (tmp_path / "greeting.txt.jinja").write_text("Hi {{ name }}\n", encoding="utf-8")
    renderer = TemplateRenderer((tmp_path, _TEMPLATES))

    assert renderer.render("greeting.txt.jinja", {"name": "Ada"}) == "Hi Ada\n"


def test_a_template_no_directory_holds_is_not_found() -> None:
    with pytest.raises(TemplateNotFound):
        _ = TemplateRenderer().render("nowhere.py.jinja", {})
