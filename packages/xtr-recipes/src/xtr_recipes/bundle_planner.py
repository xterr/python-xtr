"""BundlePlanner: settling the application's bundle list once per plan."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .bundle_entry import BundleEntry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .bundles_file import BundlesFile
    from .recipe_lock import BundleState

__all__ = ["BundlePlanner"]


@final
class BundlePlanner:
    """Decides which of a plan's candidate bundles the application must list.

    Every recipe in a plan names its bundles; the list they go in is one file,
    so the decision is made once, for all of them together. Two answers come
    out of it, and each is what the lock records:

    - *adopted* — already listed, so the environments beside it were chosen by
      the application owner and are left exactly as they are;
    - *listed* — the plan adds it.

    Every recipe bundle is listed, even one another listed bundle also
    requires: the file shows exactly what the application's dependencies
    configure, and a bundle that is both a recipe's own and a peer of another
    belongs in it as much as its requirer does. A peer with no recipe of its
    own — a transitive package's bundle — is activated by the kernel without
    being listed, and ``debug:bundles`` shows it.
    """

    def finalize(
        self,
        existing: BundlesFile,
        removed: set[str],
        candidates: Mapping[str, Mapping[str, bool]],
    ) -> tuple[BundlesFile, dict[str, BundleState]]:
        """Return the bundle list to write and what became of every candidate.

        Args:
            existing: The list as the application has it now.
            removed: Targets to take out of it — a package being unconfigured
                leaves nothing importable behind, whether it was listed by a
                sync or by hand.
            candidates: Each candidate target mapped to the environments its
                recipe would list it in, in the order the recipes named them.

        Returns:
            The new list, and each candidate's standing in it.
        """
        kept = {entry.target for entry in existing.entries if entry.target not in removed}
        states: dict[str, BundleState] = {}
        added: list[BundleEntry] = []
        for target, flags in candidates.items():
            if target in kept:
                states[target] = "adopted"
            else:
                states[target] = "listed"
                added.append(BundleEntry(target=target, flags=flags))
        return existing.removing(removed).adding(added), states
