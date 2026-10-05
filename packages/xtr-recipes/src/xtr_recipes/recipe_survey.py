"""RecipeSurvey: where every recipe of a project stands, without changing any."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from .sync_selection import SyncSelection

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .recipe_loader import Recipe

__all__ = ["RecipeSurvey"]


def _no_recipes() -> dict[str, Recipe]:
    """No installed recipes."""
    return {}


def _no_targets() -> dict[str, tuple[str, ...]]:
    """No package skipped."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class RecipeSurvey:
    """What a project's recipes are and how each stands against the lock.

    The same reading a sync starts from, stopped before anything is planned:
    enough to report a project, not enough to change it. A command that only
    tells the application owner what is configured reads this, so the rule for
    which recipes count — the direct dependencies, minus the ones whose bundle
    class the installation does not carry — is stated once.

    Attributes:
        installed: Each recipe of a direct dependency whose bundles all load,
            keyed by distribution.
        skipped: Each package left out for want of the extra that ships its
            bundle class, mapped to the targets that could not be loaded.
        selection: Where each of them stands — never configured, configured
            and current, configured and since changed, or locked and no
            longer installed.
    """

    installed: Mapping[str, Recipe] = field(default_factory=_no_recipes)
    skipped: Mapping[str, tuple[str, ...]] = field(default_factory=_no_targets)
    selection: SyncSelection = field(default_factory=SyncSelection)
