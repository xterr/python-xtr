"""Importing the application where a listed bundle is not active: setting aside what cannot import.

One :class:`Inspection` serves one application scan. A module whose import
fails because a package it needs is not installed is **inspected**: imported
once more, with that package — and each other one it turns out to need —
stood in for, to learn what it defines. The module is then **set aside**: it
is kept here, out of ``sys.modules``, and nothing it defines is registered.

Only the inspected module is lied to. The stand-ins, and the modules set
aside so far, are served to its own code alone; every other module the
inspection imports runs truthfully, and stays loaded:

- one probing for a missing package (``try: import faker``,
  ``find_spec('faker')``) learns it is missing;
- one needing it fails — and the traceback names its body — so that module is
  inspected and set aside first, and the inspection of the first one starts
  again, served the set-aside module where it imports it.

A traceback running through several bodies — a fixture importing a helper
importing what is not installed — names a chain of modules failing in turn;
each is inspected, innermost first, so each body runs once more, not once per
link. A module of a set-aside package that is not set aside itself is
inspected before the module importing it, too: it cannot be loaded under its
package.

The packages the inspected module lies in are settled before its import, so
none of their bodies runs inside it: one loaded stays as it is; one set aside
is put back for the inspection's length; one not loaded — its body was
importing the inspected module when it failed — is stood for by its bare
package, holding what its body had defined by then, until the inspection ends.

What an inspection serves is loaded only for the import statement asking for
it: it is taken out of ``sys.modules``, and off its packages, before the next
import, and put back on its packages once the inspected body has its hands
back. Outside an inspection, a set-aside module is not loaded at all, so any
module importing it fails as it would at runtime, and is inspected itself.

A module first loaded meanwhile — by the inspected body, by an earlier
attempt at it, or by the failed import before them, all of which are
recorded — may still have touched what the body built:

- one that is, lies in, or imported the inspected module, a set-aside module
  given back or a set-aside package put in place, would fail at runtime: it
  is set aside through that module, as it is, without being run again;
- one whose function the inspected body called and was served — it imports
  on the body's behalf — and one that imported such a module, are not kept:
  the scan imports each again, truthfully;
- one that lies in, or imported, a bare package put in place stays loaded:
  that package is inspected next, and the module is set aside through it
  then, without being run again.

Asking whether a module exists (``find_spec``) is not reaching it: a module
that only asked is kept.

A module loaded before keeps whatever its function, served for the inspected
body, made of a stand-in — which is warned of.

Private to the scan.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import threading
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Final, cast, final

from xtr_dependency_injection.diagnostics.report import SetAsideReport
from xtr_dependency_injection.exception import ResourceImportError

from ._frames import running_module
from ._import_tracker import ImportTracker
from ._stand_ins import ChildOfSetAside, StandInFinder

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from types import TracebackType

__all__ = ["LOCK", "Inspection", "SetAsideModule"]

LOCK: Final = threading.RLock()
"""Held for a whole inspecting scan: its import hooks and stand-ins are the process's."""

_LOGGER: Final = logging.getLogger("xtr_dependency_injection")


@dataclass(slots=True)
class SetAsideModule:
    """A module set aside, and why.

    Attributes:
        module: The module, as its inspection left it.
        missing: The top-level packages it needs that are not installed.
        through: The set-aside module it needs them through, or ``None`` when
            it imports one of them itself.
        expected: Whether it needs, or reaches, the package of a listed
            bundle that is not active.
        defines: ``module:qualname`` of each object it defines that the
            scan looked at.
    """

    module: ModuleType
    missing: set[str]
    through: str | None
    expected: bool
    defines: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Contacts:
    """What the modules first loaded during one inspected import touched.

    Attributes:
        condemned: Each to set aside, mapped to the set-aside module it is set
            aside through.
        retried: Each to import again, truthfully.
    """

    condemned: dict[str, str]
    retried: set[str]


@final
class Inspection:
    """Imports for one application scan, setting aside what needs a package not installed."""

    __slots__ = (
        "_application",
        "_inactive",
        "_inspecting",
        "_missing",
        "_partial",
        "_reached",
        "_set_aside",
        "_truthful",
    )

    def __init__(self, application: tuple[str, ...], inactive_packages: frozenset[str]) -> None:
        """Inspect for an application under ``application``.

        Args:
            application: The application package and the resources its scan
                names: a module missing from one of them is never set aside.
            inactive_packages: The packages of the listed bundles that are
                not active — a top-level package, or the subpackage of the
                application a bundle of its own lives in — which make a
                set-aside module expected.
        """
        self._application = application
        self._inactive = inactive_packages
        self._missing: set[str] = set()
        self._set_aside: dict[str, SetAsideModule] = {}
        self._inspecting: list[str] = []
        self._partial: dict[str, dict[str, object]] = {}
        # What each module imported while one module was imported, its inspections included.
        self._reached: dict[str, set[str]] = {}
        # The modules the failed import before the inspections loaded, running truthfully.
        self._truthful: frozenset[str] = frozenset()

    @property
    def set_aside(self) -> Mapping[str, SetAsideModule]:
        """Every module set aside so far, by name."""
        return self._set_aside

    def import_module(self, name: str) -> ModuleType:
        """Import ``name``, or inspect and set it aside when a package it needs is not installed.

        Raises:
            ResourceImportError: If it fails to import, and is not to be set
                aside, or still fails with what it needs stood in for.
        """
        found = self._set_aside.get(name)
        if found is not None:
            return found.module
        loaded = frozenset(sys.modules)
        self._reached = {}
        try:
            with ImportTracker(imports=self._reached):
                module = importlib.import_module(name)
        except ImportError as error:
            failure = error
        except Exception as error:
            raise ResourceImportError(name) from error
        else:
            self._drop_reloaded(loaded)
            return module
        # Inspected outside the handler: what fails meanwhile is not raised over this failure.
        missing = self._not_installed(failure)
        if missing is None:
            raise ResourceImportError(name) from failure
        self._truthful = frozenset(entry for entry in sys.modules if entry not in loaded)
        self._keep_partial(failure, inspected=None)
        # The modules it failed through fail on their own: each is inspected first, innermost first.
        for culprit in _failing_modules(failure, self._set_aside):
            if culprit != name and culprit not in self._set_aside:
                _ = self._inspect(culprit, missing, loaded)
        return self._inspect(name, missing, loaded)

    def reports(self) -> list[SetAsideReport]:
        """Return what was set aside, as the scan report holds it, and forget it."""
        reports = [
            SetAsideReport(
                module=name,
                missing=tuple(sorted(entry.missing)),
                through=entry.through,
                defines=tuple(entry.defines),
                expected=entry.expected,
            )
            for name, entry in self._set_aside.items()
        ]
        self._set_aside.clear()
        return reports

    def _drop_reloaded(self, loaded: frozenset[str]) -> None:
        """Take out again each set-aside module an import that succeeded ran afresh.

        A module importing a set-aside package optionally (``try: import
        app.seeds``) runs it, and what it imports, truthfully: what of it was
        set aside is not left loaded.
        """
        for entry in [entry for entry in sys.modules if entry not in loaded]:
            if _holder(entry, self._set_aside) is not None:
                _drop(entry, sys.modules[entry])

    def _not_installed(self, error: ImportError) -> str | None:
        """Return the top-level package ``error`` found missing, when it is not installed.

        An import error a library raised over the missing module — "install
        the extra", naming no module — is read through to it. ``None`` — the
        failure is not one to set aside — for a module missing from the
        application, or from a package that is installed, and for an import
        error naming a module of its own: that is a broken installation, or a
        mistake in the code.
        """
        missing = _missing_module(error)
        if missing is None or not missing.name:
            return None
        package = missing.name.partition(".")[0]
        if package in self._missing:
            return package
        if any(package == root.partition(".")[0] for root in self._application):
            return None
        if package in sys.modules:
            return None
        return package if importlib.util.find_spec(package) is None else None

    def _inspect(self, name: str, missing: str, loaded: frozenset[str]) -> ModuleType:
        """Import ``name`` with what it needs stood in for, and set it aside.

        A module ``name`` imports that fails for a package not installed is
        inspected, and set aside, first. ``loaded`` is what was loaded before
        the scan first tried ``name``.

        Raises:
            ResourceImportError: If it still fails to import, or the modules
                failing import one another.
        """
        self._missing.add(missing)
        self._inspecting.append(name)
        try:
            while True:
                found = self._set_aside.get(name)
                if found is not None:
                    # Set aside, meanwhile, through a module inspected before it.
                    return found.module
                module, chain, package = self._attempt(name, loaded)
                if module is not None:
                    return module
                self._missing.add(package)
                for culprit in chain:
                    if culprit not in self._set_aside:
                        _ = self._inspect(culprit, package, loaded)
        finally:
            _ = self._inspecting.pop()

    def _attempt(
        self, name: str, loaded: frozenset[str]
    ) -> tuple[ModuleType | None, list[str], str]:
        """Import ``name`` once, inspected; return it, or what to inspect before it, and why.

        The modules to inspect first come innermost first, with the package
        found missing; none, and that package, when ``name`` needs it itself.

        Raises:
            ResourceImportError: If it fails for anything else.
        """
        finder = StandInFinder(
            frozenset(self._missing),
            name,
            {entry: found.module for entry, found in self._set_aside.items()},
        )

        def restore() -> None:
            # The inspected body has its hands back: what it was served is on its packages again.
            if running_module() == name:
                finder.restore()

        tracker = ImportTracker(before=finder.sweep, after=restore, imports=self._reached)
        placed = self._place_packages(name)
        module: ModuleType | None = None
        failure: ImportError | None = None
        contacts = _Contacts({}, set())
        sys.meta_path.insert(0, finder)
        try:
            with tracker:
                module = importlib.import_module(name)
        except ImportError as error:
            failure = error
        except Exception as error:
            raise _still_failing(name, error, finder) from error
        finally:
            sys.meta_path.remove(finder)
            finder.close()
            contacts, held = self._tidy(name, loaded, finder, placed)
        if failure is not None or module is None:
            chain, package = self._first(name, failure, finder)
            return None, chain, package
        self._warn_lent(name, finder, loaded)
        self._set_aside[name] = self._entry(name, module, finder, tracker, placed)
        for entry, through in contacts.condemned.items():
            if entry in self._set_aside:
                continue
            source = self._set_aside[through]
            self._set_aside[entry] = SetAsideModule(
                held[entry], set(source.missing), through, source.expected
            )
        return module, [], ""

    def _tidy(
        self,
        name: str,
        loaded: frozenset[str],
        finder: StandInFinder,
        placed: list[tuple[str, ModuleType]],
    ) -> tuple[_Contacts, dict[str, ModuleType]]:
        """Take out what one attempt at ``name`` left loaded that cannot stay.

        A module to set aside whose body ran only in the failed import before
        the inspections stays loaded, as a failed import leaves it: it holds no
        stand-in, and a package importing it again finds it there, as it would
        at runtime, instead of running it twice.

        Returns what the modules first loaded meanwhile touched, and each
        module to set aside, as it is.
        """
        inspected = sys.modules.get(name)
        if inspected is not None:
            _drop(name, inspected)
        for package_name, package_module in reversed(placed):
            _drop(package_name, package_module)
        contacts = self._contacts(name, loaded, finder, [package for package, _ in placed])
        held = {entry: sys.modules[entry] for entry in contacts.condemned}
        for entry in [*contacts.condemned, *contacts.retried]:
            if entry in contacts.retried or entry not in self._truthful:
                _drop(entry, sys.modules[entry])
        return contacts, held

    def _contacts(
        self,
        name: str,
        loaded: frozenset[str],
        finder: StandInFinder,
        placed: Collection[str],
    ) -> _Contacts:
        """Sort the modules first loaded while ``name`` was tried by what they touched.

        Only the inspected module, the set-aside modules given back and the
        packages put in place carry what the body built: a module that merely
        asked for a missing package was answered truthfully, and is kept. A
        bare package put in place is inspected next: what touched it is left
        for that inspection.
        """
        fresh = [entry for entry in sys.modules if entry not in loaded]
        failing = {name, *finder.modules_served, *(p for p in placed if p in self._set_aside)}
        condemned: dict[str, str] = {}
        retried: set[str] = set()
        changed = True
        while changed:
            changed = False
            for entry in fresh:
                if entry in condemned:
                    continue
                reached = self._reached.get(entry, set())
                source = _holder(entry, failing) or next(
                    (
                        found
                        for target in reached
                        if (found := _holder(target, failing | condemned.keys())) is not None
                    ),
                    None,
                )
                if source is not None:
                    condemned[entry] = condemned.get(source, source)
                    retried.discard(entry)
                    changed = True
                elif entry not in retried and (
                    entry in finder.lent_to
                    or any(_holder(target, retried) is not None for target in reached)
                ):
                    retried.add(entry)
                    changed = True
        return _Contacts(condemned, retried)

    def _place_packages(self, name: str) -> list[tuple[str, ModuleType]]:
        """Settle each package ``name`` lies in that is not loaded; return those put in place.

        Outermost first: a set-aside one is put back as it is; any other is
        its bare package, built from where it is found, its body not run —
        holding what that body had defined when its import last failed.
        """
        placed: list[tuple[str, ModuleType]] = []
        parts = name.split(".")
        for index in range(1, len(parts)):
            package = ".".join(parts[:index])
            if package in sys.modules:
                continue
            found = self._set_aside.get(package)
            if found is not None:
                module = found.module
            else:
                location = importlib.util.find_spec(package)
                if location is None:  # pragma: no cover — a package its module was found in
                    break
                module = importlib.util.module_from_spec(location)
                vars(module).update(self._partial.get(package, {}))
            sys.modules[package] = module
            holder_name, _, child = package.rpartition(".")
            if holder_name:
                setattr(sys.modules[holder_name], child, module)
            placed.append((package, module))
        return placed

    def _keep_partial(self, error: BaseException, *, inspected: str | None) -> None:
        """Keep what each body ``error`` ran through had defined, but the one inspected.

        A package whose body failed may be stood for by its bare package
        later: it then holds what its body had defined before it failed.
        """
        traceback: TracebackType | None = error.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame
            body = frame.f_globals.get("__name__")
            if (
                frame.f_code.co_name == "<module>"
                and isinstance(body, str)
                and body != inspected
                and body not in sys.modules
            ):
                namespace = cast("dict[str, object]", frame.f_globals)
                self._partial[body] = {
                    key: value
                    for key, value in namespace.items()
                    if not (key.startswith("__") and key.endswith("__"))
                }
            traceback = traceback.tb_next

    def _warn_lent(self, name: str, finder: StandInFinder, loaded: frozenset[str]) -> None:
        """Warn of each module loaded before, and kept, whose function ``name`` had served."""
        for lent in sorted(finder.lent_to):
            if lent in loaded and lent in sys.modules:
                _LOGGER.warning(
                    (
                        "While inspecting %s, a function of %s it called was handed a stand-in "
                        "for %s, not installed here; whatever %s keeps of it stays until the "
                        "process ends."
                    ),
                    name,
                    lent,
                    ", ".join(sorted(finder.packages_served)),
                    lent,
                )

    def _first(
        self, name: str, error: ImportError | None, finder: StandInFinder
    ) -> tuple[list[str], str]:
        """Return the modules to inspect before ``name``, innermost first, and the package lacked.

        Raises:
            ResourceImportError: If the failure is not for a package not
                installed, ``name`` itself fails for one it was given, or the
                modules failing import one another.
        """
        if error is None:  # pragma: no cover — an import gives back its module or raises
            raise ResourceImportError(name)
        signal = _signal(error)
        if signal is not None:
            if signal.child in self._inspecting:
                raise _still_failing(name, error, finder) from error
            lacking = sorted(self._set_aside[signal.parent].missing) or sorted(self._missing)
            return [signal.child], lacking[0]
        package = self._not_installed(error)
        if package is None:
            raise _still_failing(name, error, finder) from error
        # The inspected package's own namespace too: a module of it inspected next stands under it.
        self._keep_partial(error, inspected=None)
        chain = [body for body in _failing_modules(error, self._set_aside) if body != name]
        stuck = not chain and package in self._missing
        if stuck or any(body in self._inspecting for body in chain):
            raise _still_failing(name, error, finder) from error
        return chain, package

    def _entry(
        self,
        name: str,
        module: ModuleType,
        finder: StandInFinder,
        tracker: ImportTracker,
        placed: list[tuple[str, ModuleType]],
    ) -> SetAsideModule:
        """Say why ``name`` is set aside: what it was served or lies in, and what it reached."""
        through_names = [package for package, _ in placed if package in self._set_aside]
        through_names.extend(
            served for served in finder.modules_served if served not in through_names
        )
        through_modules = [self._set_aside[served] for served in through_names]
        missing = set(finder.packages_served)
        for served in through_modules:
            missing.update(served.missing)
        through = None if finder.packages_served else next(iter(through_names), None)
        reached = tracker.imports.get(name, set()) | tracker.lookups.get(name, set())
        expected = (
            any(self._is_inactive(package) for package in missing)
            or any(self._is_inactive(target) for target in reached)
            or any(served.expected for served in through_modules)
        )
        return SetAsideModule(module, missing, through, expected)

    def _is_inactive(self, module: str) -> bool:
        """Whether ``module`` belongs to the package of a listed bundle that is not active."""
        return _holder(module, self._inactive) is not None


def _missing_module(error: BaseException) -> ModuleNotFoundError | None:
    """Return ``error`` if a module is missing, else the missing-module error it was raised over.

    Read through an import error naming no module — a library's "install the
    extra" — or naming the package found missing. One naming another module
    (``cannot import name 'X' from 'app.y'``) is a failure of its own,
    whatever it was raised over.
    """
    seen: set[int] = set()
    named: str | None = None
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, ModuleNotFoundError):
            found = current.name.partition(".")[0] if current.name else None
            return current if named is None or found == named else None
        if isinstance(current, ImportError) and current.name is not None and named is None:
            named = current.name.partition(".")[0]
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None


def _signal(error: BaseException) -> ChildOfSetAside | None:
    """Return the :class:`ChildOfSetAside` ``error`` is, or was raised over; ``None`` if none."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, ChildOfSetAside):
            return current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None


def _failing_modules(error: BaseException, set_aside: Mapping[str, object]) -> list[str]:
    """Return the modules whose bodies failed, innermost first, as ``error``'s traceback shows.

    The error ran through each body, so each fails while the one inside it
    does. A set-aside module run again by a truthful import fails as it
    always did: the module that imported it is the one to inspect.
    """
    bodies: list[str] = []
    traceback: TracebackType | None = error.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame
        name = frame.f_globals.get("__name__")
        if frame.f_code.co_name == "<module>" and isinstance(name, str) and name not in bodies:
            bodies.append(name)
        traceback = traceback.tb_next
    return [body for body in reversed(bodies) if body not in set_aside]


def _still_failing(name: str, error: BaseException, finder: StandInFinder) -> ResourceImportError:
    """Return the failure of ``name``, imported again with what it needs stood in for."""
    failure = ResourceImportError(name)
    if finder.packages_served:
        packages = ", ".join(repr(package) for package in sorted(finder.packages_served))
        served = f"with {packages} stood in for — not installed here —"
    else:
        served = "with the modules it needs set aside given back"
    note = f"imported again {served} to see what it defines, it failed with {error!r}"
    missing = _missing_module(error)
    lacked = missing.name.partition(".")[0] if missing is not None and missing.name else None
    if lacked is not None and lacked in finder.packages_served:
        note += (
            f"; {lacked!r} is stood in for only where this module's own code imports it — "
            "not for code run with no module name, nor on another thread"
        )
    failure.add_note(note)
    return failure


def _drop(name: str, module: ModuleType) -> None:
    """Take ``module`` out of ``sys.modules`` and off its package: importing it runs it afresh."""
    if sys.modules.get(name) is module:
        del sys.modules[name]
    parent, _, child = name.rpartition(".")
    holder = sys.modules.get(parent) if parent else None
    if holder is not None and getattr(holder, child, None) is module:
        delattr(holder, child)


def _holder(module: str, packages: Collection[str]) -> str | None:
    """Return the one of ``packages`` that ``module`` is, or lies in; ``None`` if none."""
    return next(
        (package for package in packages if module == package or module.startswith(f"{package}.")),
        None,
    )
