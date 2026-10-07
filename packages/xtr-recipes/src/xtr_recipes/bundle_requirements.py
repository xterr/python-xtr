"""BundleRequirements: which bundles of a set another bundle in it already requires."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection.bundle import Bundle
from xtr_dependency_injection.bundle.required_bundle import required_bundles_of

from .normalise import normalise

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from xtr_dependency_injection.bundle.bundle import AnyBundle

__all__ = ["BundleRequirements"]


@final
class BundleRequirements:
    """Tells which bundles of a set another bundle in that set requires.

    A bundle that declares a required peer brings it along by itself, so naming
    that peer in the application's bundle list adds nothing — the logging bundle
    requires the clock bundle, and an application depending on both lists only
    logging. A recipe's bundle is therefore left out while something else in the
    final set reaches it, and that is recomputed every sync: once the requirer
    goes away, the bundle is listed on its own.

    A requirement names its peer as a class or as a ``"module:Class"`` string,
    and a bundle is usually re-exported from its package's ``bundle`` package,
    so one class has two spellings. Both sides are resolved to classes wherever
    they load and compared by identity, falling back to the string.
    """

    __slots__ = ("_loader",)

    def __init__(self, loader: Callable[[str], type[AnyBundle] | None] | None = None) -> None:
        """Resolve ``"module:Class"`` with ``loader``, or by import when none is given."""
        self._loader: Callable[[str], type[AnyBundle] | None] = (
            loader if loader is not None else _import_bundle
        )

    def loadable(self, target: str, distribution: str) -> bool:
        """Whether ``target`` names a loadable bundle of ``distribution``'s own package.

        Resolving a target imports its module, so a recipe may only name a
        bundle under its own distribution's import package: a manifest naming
        ``os:system`` or another package's module would otherwise make a sync
        import whatever it points at. A target outside the package, or one the
        installation cannot load — a package installed without the extra that
        brings its container integration — is reported as not loadable, so a
        sync skips the recipe and retries next time.
        """
        return _under(target, distribution) and self._loader(target) is not None

    def required(
        self,
        targets: Collection[str],
        requirers: Collection[str],
    ) -> frozenset[str]:
        """Return the members of ``targets`` that another member requires.

        Follows required peers from every member that loads, hard and soft
        declarations alike, and through peers outside ``targets`` as well: a
        peer is activated by its requirer, so whatever that peer requires in
        turn is activated too. A member whose class cannot be loaded requires
        nothing, but can still be found by the string a requirement names.

        Args:
            targets: The bundle targets, ``"module:Class"``, of the final set.
            requirers: The members whose requirements count. A bundle active in
                some environments only activates its peers there only, so it
                cannot stand in for listing them.

        Returns:
            Those of them something else in the set reaches; listing them would
            be redundant.
        """
        members = {target: self._loader(target) for target in dict.fromkeys(targets)}
        owners: dict[type[AnyBundle], str] = {}
        for target, loaded in members.items():
            if loaded is not None:
                _ = owners.setdefault(loaded, target)
        found: set[str] = set()
        roots = set(requirers)
        pending = [
            loaded for target, loaded in members.items() if loaded is not None and target in roots
        ]
        expanded: set[type[AnyBundle]] = set()
        while pending:
            requirer = pending.pop()
            if requirer in expanded:
                continue
            expanded.add(requirer)
            for declaration in required_bundles_of(requirer):
                peer = declaration.target
                name = peer if isinstance(peer, str) else _name_of(peer)
                resolved = self._loader(peer) if isinstance(peer, str) else peer
                member = owners.get(resolved) if resolved is not None else None
                if member is not None:
                    found.add(member)
                elif name in members:
                    found.add(name)
                if resolved is not None:
                    pending.append(resolved)
        return frozenset(found)


def _name_of(bundle: type[AnyBundle]) -> str:
    """Return the ``"module:Class"`` target naming ``bundle``."""
    return f"{bundle.__module__}:{bundle.__qualname__}"


def _under(target: str, distribution: str) -> bool:
    """Whether ``target``'s module belongs to ``distribution``'s import package.

    A distribution name is compared however it was spelled, and its import
    package is that name with every separator turned to an underscore —
    ``xtr-messenger`` ships ``xtr_messenger``. A dotted name is its own
    spelling of a namespace package, so ``zope-interface`` is also read as
    ``zope.interface``; a target names one of those two packages or a module
    inside it.
    """
    module = target.partition(":")[0]
    name = normalise(distribution)
    return any(
        module == package or module.startswith(f"{package}.")
        for package in (name.replace("-", "_"), name.replace("-", "."))
    )


def _import_bundle(target: str) -> type[AnyBundle] | None:
    """Return the bundle class ``"module:Class"`` names, or ``None``.

    A target that does not load — a package installed without its container
    integration, or a name that turns out not to be a bundle — is reported as
    absent rather than raised over: a sync skips it and says which extra to
    install, and a requirement walk treats it as requiring nothing.
    """
    module_name, _, class_name = target.partition(":")
    if not module_name or not class_name:
        return None
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    loaded = cast("object", getattr(module, class_name, None))
    if not (isinstance(loaded, type) and issubclass(loaded, Bundle)):
        return None
    return cast("type[AnyBundle]", loaded)
