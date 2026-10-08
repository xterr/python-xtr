"""ProjectName: the one name a project goes by, as a distribution and as a package."""

from __future__ import annotations

import keyword
import re
import sys
from dataclasses import dataclass
from typing import final

from .exception import InvalidProjectNameError

__all__ = ["ProjectName"]

# Anything but a lowercase letter or a digit separates words; a run of them is one dash.
_SEPARATORS = re.compile(r"[^a-z0-9]+")


@final
@dataclass(frozen=True, slots=True)
class ProjectName:
    """A project's name, normalised once and used everywhere it appears.

    The distribution name is also the console script, so ``uv run <name>``
    reads as the project's own command; the import name is the package under
    ``src/`` that the kernel scans.

    Attributes:
        distribution: The lowercase, dash-separated name in ``[project].name``.
        app: The import name: the distribution with its dashes as underscores.
    """

    distribution: str
    app: str

    @classmethod
    def parse(cls, text: str) -> ProjectName:
        """Normalise ``text`` — a ``--name`` or a directory's name — into a project name.

        Raises:
            InvalidProjectNameError: When nothing is left once normalised, or the
                import name it gives is not an identifier, is a keyword, or is
                a module of the standard library the application would shadow.
        """
        distribution = _SEPARATORS.sub("-", text.strip().lower()).strip("-")
        if not distribution:
            raise InvalidProjectNameError(text, "it holds no letter or digit")
        app = distribution.replace("-", "_")
        if not app.isidentifier():
            raise InvalidProjectNameError(text, f"{app!r} is not a valid import name")
        if keyword.iskeyword(app):
            raise InvalidProjectNameError(text, f"{app!r} is a Python keyword")
        if app in sys.stdlib_module_names:
            raise InvalidProjectNameError(text, f"{app!r} would shadow the standard library")
        return cls(distribution=distribution, app=app)
