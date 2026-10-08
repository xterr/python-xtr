"""AddOn: a package a new project can start with, beyond what its template brings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["AddOn"]


@final
@dataclass(frozen=True, slots=True)
class AddOn:
    """One entry of the add-on table: a short name standing for a requirement.

    Choosing an add-on only adds its requirement; the recipe the package ships
    does the rest of the configuring, the way it would for a package added later.

    Attributes:
        name: What ``--with`` calls it.
        summary: One line on what it brings, shown when the add-ons are offered.
        distribution: The package it installs.
        extras: The extras always installed with it — its bundle's among them.
        variants: The further extras a project picks between, such as database
            drivers; written after the name as ``orm:sqlite+postgres``.
        default_variants: The variants chosen when the name is given alone.
        variant_label: What the variants are, for the question that offers them.
        templates: The templates it fits; empty when it fits every one.
    """

    name: str
    summary: str
    distribution: str
    extras: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    default_variants: tuple[str, ...] = ()
    variant_label: str = "extras"
    templates: tuple[str, ...] = ()

    def requirement(self, variants: Sequence[str]) -> str:
        """Return the requirement installing this add-on with ``variants``."""
        extras = (*self.extras, *variants)
        if not extras:
            return self.distribution
        return f"{self.distribution}[{','.join(extras)}]"

    def fits(self, template: str) -> bool:
        """Report whether a project made from ``template`` can take this add-on."""
        return not self.templates or template in self.templates
