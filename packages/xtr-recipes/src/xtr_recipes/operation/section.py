"""Section: the heading that says what is about to happen to one package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

__all__ = ["Section"]


@final
@dataclass(frozen=True, slots=True)
class Section:
    """Announces the package the following steps belong to.

    The only unindented step besides the two whole-project writes, so a plan
    reads as one block per package.

    Attributes:
        action: What is being done — ``configure``, ``update``,
            ``unconfigure`` or ``skip``.
        package: The distribution it is being done to.
    """

    changes: ClassVar[bool] = False

    action: str
    package: str

    def render(self) -> tuple[str, ...]:
        """Return the heading line."""
        return (f"{self.action} {self.package}",)

    def apply(self) -> None:
        """Do nothing: a heading only introduces the steps under it."""
