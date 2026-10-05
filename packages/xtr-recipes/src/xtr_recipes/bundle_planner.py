"""BundlePlanner: settling the application's bundle list once per plan."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .bundle_entry import BundleEntry

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from .bundle_requirements import BundleRequirements
    from .bundles_file import BundlesFile
    from .recipe_lock import BundleState

__all__ = ["BundlePlanner"]


@final
class BundlePlanner:
    """Decides which of a plan's candidate bundles the application must list.

    Every recipe in a plan names its bundles; the list they go in is one file,
    so the decision is made once, for all of them together. Three answers come
    out of it, and each is what the lock records:

    - *adopted* — already listed, so the environments beside it were chosen by
      the application owner and are left exactly as they are;
    - *required* — something else in the final list requires it, so listing it
      adds nothing. Recomputed every plan: once the requirer goes, the bundle
      is listed on its own;
    - *listed* — neither, so the plan adds it.
    """

    __slots__ = ("_requirements",)

    def __init__(self, requirements: BundleRequirements) -> None:
        """Ask ``requirements`` which candidates something else already reaches."""
        self._requirements = requirements

    def finalize(
        self,
        existing: BundlesFile,
        removed: set[str],
        candidates: Mapping[str, Mapping[str, bool]],
        still_required: Collection[str] = (),
    ) -> tuple[BundlesFile, dict[str, BundleState]]:
        """Return the bundle list to write and what became of every candidate.

        Args:
            existing: The list as the application has it now.
            removed: Targets to take out of it — a package being unconfigured
                leaves nothing importable behind, whether it was listed by a
                sync or by hand.
            candidates: Each candidate target mapped to the environments its
                recipe would list it in, in the order the recipes named them.
            still_required: Targets to keep as required whatever the walk
                finds: while a requirer's class does not load, the walk cannot
                see what it requires, and listing its peers would leave
                entries behind once the installation is mended.

        Returns:
            The new list, and each candidate's standing in it.
        """
        kept_entries = tuple(entry for entry in existing.entries if entry.target not in removed)
        base = tuple(entry.target for entry in kept_entries)
        everywhere = [
            target
            for target, flags in (
                *((entry.target, entry.flags) for entry in kept_entries),
                *candidates.items(),
            )
            if _everywhere(flags)
        ]
        required = self._requirements.required((*base, *candidates), everywhere)
        kept = set(base)
        states: dict[str, BundleState] = {}
        added: list[BundleEntry] = []
        for target, flags in candidates.items():
            if target in kept:
                states[target] = "adopted"
            elif target in required or target in still_required:
                states[target] = "required"
            else:
                states[target] = "listed"
                added.append(BundleEntry(target=target, flags=flags))
        return existing.removing(removed).adding(added), states


def _everywhere(flags: Mapping[str, bool]) -> bool:
    """Whether a bundle listed with ``flags`` is active in every environment.

    Only such a bundle can stand in for listing what it requires: one limited
    to ``dev`` and ``test`` would leave its peers inactive in ``prod``.
    """
    return flags.get("all", False) and all(flags.values())
