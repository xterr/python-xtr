"""TemplateRenderer: a template and its values in, source that parses out."""

from __future__ import annotations

import ast
from importlib.resources import files
from typing import TYPE_CHECKING, Final, final

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .exception import GeneratedSourceError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = ["TemplateRenderer"]

_PYTHON_TEMPLATE: Final = ".py.jinja"
"""The ending of a template that renders Python source, which is parsed before it is used."""


@final
class TemplateRenderer:
    """Renders the makers' templates, and checks that Python source comes out.

    Templates are read from the directories given, then from the
    ``templates`` directory shipped in this package, so a directory listed
    first can replace a shipped template of the same name. A value a template
    names but the maker did not pass is an error, never an empty string, and
    nothing is escaped: the output is code, not markup.

    Every template ending in ``.py.jinja`` is parsed once rendered. A template
    that renders source with a syntax error — through its own fault or a value
    passed to it — raises :class:`GeneratedSourceError` rather than handing the
    application a module that fails at import.
    """

    __slots__ = ("_environment",)

    def __init__(self, template_dirs: Sequence[Path] = ()) -> None:
        """Read templates from ``template_dirs``, then from this package's ``templates``."""
        shipped = str(files("xtr_maker").joinpath("templates"))
        self._environment = Environment(
            loader=FileSystemLoader([*map(str, template_dirs), shipped]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            autoescape=False,  # noqa: S701 — renders Python source, never HTML.
        )

    def render(self, template: str, context: Mapping[str, object]) -> str:
        """Render ``template`` with ``context``.

        Args:
            template: The template's path under a template directory,
                ``/``-separated.
            context: The values the template reads.

        Returns:
            The rendered text.

        Raises:
            GeneratedSourceError: When ``template`` ends in ``.py.jinja`` and
                what it rendered does not parse as Python.
            jinja2.TemplateNotFound: When no template directory holds ``template``.
            jinja2.UndefinedError: When the template reads a value ``context``
                does not hold.
        """
        source = self._environment.get_template(template).render(context)
        if template.endswith(_PYTHON_TEMPLATE):
            try:
                _ = ast.parse(source, filename=template)
            except SyntaxError as error:
                raise GeneratedSourceError(template, error.msg, error.lineno) from error
        return source
