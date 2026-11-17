"""Finds a template in whichever installed package ships it."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from jinja2 import BaseLoader, TemplateNotFound
from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable

    from jinja2 import Environment

__all__ = ["TemplateLoader"]

_TEMPLATES: Final = "templates"


@final
class TemplateLoader(BaseLoader):
    """Loads ``"@<import package>/<path>"`` from the ``templates/`` folder of that package.

    A library shipping a data collector ships its panel's template as a
    package file — ``src/xtr_orm/templates/collector/orm.html.j2`` is
    ``"@xtr_orm/collector/orm.html.j2"`` — and needs no template engine of its
    own. A name of any other shape, a package that is not installed, or a
    path stepping out with ``..`` is not found.

    A template read from a file on disk is reloaded once the file changes,
    so a panel being written shows its last version.
    """

    @override
    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        """Return the source of ``template``, its file, and whether it is still current.

        Raises:
            TemplateNotFound: When the name has no package, the package is not
                installed, the path leaves its folder, or there is no such file.
        """
        del environment
        package, separator, path = template.removeprefix("@").partition("/")
        parts = path.split("/")
        if not template.startswith("@") or not separator or not package or ".." in parts:
            raise TemplateNotFound(template)
        try:
            root = importlib.resources.files(package) / _TEMPLATES
        except ModuleNotFoundError as error:
            raise TemplateNotFound(template) from error
        resource = root.joinpath(*parts)
        if not resource.is_file():
            raise TemplateNotFound(template)
        source = resource.read_text("utf-8")
        if not isinstance(resource, Path):
            return source, None, None
        modified = resource.stat().st_mtime

        def current() -> bool:
            return resource.is_file() and resource.stat().st_mtime == modified

        return source, str(resource), current
