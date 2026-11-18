"""Which panels a profile has, and what each block of a panel renders to."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from jinja2 import TemplateNotFound
from markupsafe import Markup

from xtr_web_profiler.exception.template_not_found_error import TemplateNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jinja2 import Environment
    from xtr_http_kernel.data_collector import DataCollectorTemplates
    from xtr_http_kernel.profiler import Profile, Profiler

__all__ = ["TemplateManager"]


@final
class TemplateManager:
    """Pairs a profile's collectors with their panel templates, and renders a template's blocks.

    A panel template defines up to four blocks — ``toolbar`` (the toolbar
    item), ``menu`` (the profile page's menu entry), ``panel`` (the panel
    itself) and ``head`` (anything the panel needs in the page head) — and
    each is rendered on its own, so the toolbar and the profile page draw
    from one template per collector.
    """

    __slots__ = ("_environment", "_templates")

    def __init__(self, environment: Environment, templates: DataCollectorTemplates) -> None:
        """Render with ``environment`` the panels ``templates`` names."""
        self._environment = environment
        self._templates = templates

    def get_names(self, profile: Profile, profiler: Profiler) -> list[tuple[str, str]]:
        """Return the ``(collector, template)`` pairs of ``profile``'s panels, in panel order.

        A panel is shown when its collector is registered and kept data in
        this profile.

        Raises:
            TemplateNotFoundError: When a collector names a template that does
                not exist.
        """
        names: list[tuple[str, str]] = []
        for name, template in self._templates.entries:
            if not (profiler.has(name) and profile.has_collector(name)):
                continue
            try:
                _ = self._environment.get_template(template)
            except TemplateNotFound as error:
                raise TemplateNotFoundError(name, template) from error
            names.append((name, template))
        return names

    def render_block(self, template: str, block: str, context: Mapping[str, object]) -> Markup:
        """Return ``block`` of ``template`` rendered with ``context``; empty when it has none."""
        loaded = self._environment.get_template(template)
        render = loaded.blocks.get(block)
        if render is None:
            return Markup("")
        # Rendered by an autoescaping environment: every value in it was escaped already.
        return Markup("".join(render(loaded.new_context(dict(context)))))  # noqa: S704 — escaped by the environment

    def render(self, template: str, context: Mapping[str, object]) -> str:
        """Return the whole of ``template`` rendered with ``context``."""
        return self._environment.get_template(template).render(dict(context))
