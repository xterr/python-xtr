"""BundleEntry: one bundle listed in ``BUNDLES``, with the flags beside it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["BundleEntry"]


@final
@dataclass(frozen=True, slots=True)
class BundleEntry:
    """One line of an application's ``BUNDLES``: a bundle, and where it is active.

    The bundle is held as the ``"module:Class"`` string a recipe and the lock
    already use, so the same spelling travels from a manifest through the lock
    into the generated file without being translated on the way.

    Attributes:
        target: The bundle class as ``"module:Class"``.
        flags: Each environment name mapped to whether the bundle is active in
            it; ``{"all": True}`` means every environment. The order is kept,
            because it is the order the rendered line shows.
        by_name: Whether the line names the bundle by ``target`` itself, as a
            string key, rather than importing its class. The kernel imports a
            bundle listed by name only in an environment its flags activate it
            in, which is how a development dependency's bundle is listed: a
            deployment does not install the dependency, and an import at the
            top of the file would stop the application loading there.
    """

    target: str
    flags: Mapping[str, bool]
    by_name: bool = False

    @property
    def module(self) -> str:
        """The module the bundle class is imported from."""
        return self.target.partition(":")[0]

    @property
    def class_name(self) -> str:
        """The bundle class's own name, as the mapping key spells it when the class is imported."""
        return self.target.partition(":")[2]
