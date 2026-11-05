"""BundleRequirements: which bundle targets a recipe names actually load."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection.bundle import Bundle

from .normalise import normalise

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection.bundle.bundle import AnyBundle

__all__ = ["BundleRequirements"]


@final
class BundleRequirements:
    """Tells which bundle targets load, so a sync can skip the rest.

    A recipe names its bundles as ``"module:Class"`` targets, and a sync may
    only list one whose class the installation actually carries: a broken
    installation, or a module a bundle needs missing, would otherwise leave
    the application with a bundle list that cannot be imported. A target that
    does not load is reported as not loadable, so the recipe is skipped and
    retried on the next sync.
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
        installation cannot load, is reported as not loadable, so a sync skips
        the recipe and retries next time.
        """
        return _under(target, distribution) and self._loader(target) is not None


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

    A target that does not load — a module that cannot be imported, such as
    an optional peer's that is not installed, or a name that turns out not to
    be a bundle — is reported as absent rather than raised over: a sync skips
    the recipe and says so.
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
