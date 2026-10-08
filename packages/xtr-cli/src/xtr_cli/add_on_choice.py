"""AddOnChoice: an add-on as a project chose it, variants and all."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from .add_on import AddOn

__all__ = ["AddOnChoice"]


@final
@dataclass(frozen=True, slots=True)
class AddOnChoice:
    """An add-on and the variants picked for it.

    Attributes:
        add_on: The add-on chosen.
        variants: The variants picked, in the order the add-on lists them.
    """

    add_on: AddOn
    variants: tuple[str, ...]

    @property
    def requirement(self) -> str:
        """The requirement ``uv add`` is given for this choice."""
        return self.add_on.requirement(self.variants)

    @property
    def spelling(self) -> str:
        """How ``--with`` writes this choice, so a command line can repeat it.

        The bare name when the variants are the defaults, which it stands for.
        """
        if self.variants == self.add_on.default_variants:
            return self.add_on.name
        return f"{self.add_on.name}:{'+'.join(self.variants)}"
