"""What a set-aside module is inspected with: stand-ins for the packages that are not installed.

A module the application scan cannot import, because a package it needs is not
installed, is imported once more to learn what it defines. For that one
import, and for that module's body alone, each such package is answered by a
:class:`StandInModule`, and every name taken from it by a :class:`StandIn`: an
object that can be imported, subclassed, subscripted, called, compared,
counted and read, so module-level code built on the missing package runs to
its end. Nothing it produces is used afterwards: the module is set aside, then
dropped.

Private to the scan.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import threading
from types import BuiltinFunctionType, FunctionType, ModuleType
from typing import TYPE_CHECKING, Final, cast, final, override

from ._frames import importing_module, running_module

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

__all__ = [
    "STAND_IN_ATTRIBUTE",
    "ChildOfSetAside",
    "StandIn",
    "StandInFinder",
    "StandInModule",
    "unwrapped",
]

STAND_IN_ATTRIBUTE: Final = "__xtr_stand_in__"
"""Set on a class standing in as a base, to the dotted name it stands for."""

_DECORATED_TYPES: Final = (
    type,
    FunctionType,
    BuiltinFunctionType,
    staticmethod,
    classmethod,
    property,
)
"""What a decorator is handed: a class, or what a function definition makes."""


@final
class StandIn:
    """Stands for anything taken from a package that is not installed.

    Every attribute, item, call and operation is another stand-in, named
    after the path that reached it. A call handed exactly one class or
    function — or a stand-in remembering one — *remembers* it, since whether it
    is a decorator (``@lib.register``) or a decorator factory
    (``@lib.depends_on(Users)``) cannot be told yet:

    - a remembering stand-in, called in turn with one class or function,
      returns that argument — the factory's decorator gave back what it
      decorated;
    - it reads the remembered object's attributes — a stand-in for one the
      object lacks — and is derived from as that class, only when no module
      loaded truthfully defines it: the inspected module's own, or a
      set-aside one's. Of a class of a module that is loaded, it reads
      nothing and derives from nothing, so no code of that module runs;
    - it sets attributes on the object only when the inspected module
      defines it — a decorator applied over it still marks the class it
      decorates, and nothing of another module is changed;
    - :func:`unwrapped` gives back the object, for the scan to see what a
      module defines.

    Called as a metaclass — a name, a tuple of bases, a namespace — it builds
    the class. As a base it is a plain class of its own, marked with
    :data:`STAND_IN_ATTRIBUTE`.
    """

    __slots__ = ("_base", "_path", "_remembered")

    _path: str
    _base: type | None
    _remembered: object | None

    def __init__(self, path: str, remembered: object | None = None) -> None:
        """Stand for ``path``, the dotted name it was reached by, remembering ``remembered``."""
        self._path = path
        self._base = None
        self._remembered = remembered

    def __getattr__(self, name: str) -> object:
        """Return the remembered object's ``name`` where it may be read, else a stand-in for it.

        A dunder neither has is answered as by any object without it.
        """
        if self._remembered is not None and _readable(self._remembered):
            try:
                return cast("object", getattr(self._remembered, name))
            except AttributeError:
                pass
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return StandIn(f"{self._path}.{name}")

    @override
    def __setattr__(self, name: str, value: object) -> None:
        """Set one of its own slots; else ``name`` on the remembered object of this module.

        Only an object the module running now defines — the one inspected —
        is changed: a factory handed a class of another module leaves it be.
        """
        if name in StandIn.__slots__:
            object.__setattr__(self, name, value)
        elif (
            self._remembered is not None
            and getattr(self._remembered, "__module__", None) == running_module()
        ):
            setattr(self._remembered, name, value)

    def __call__(self, *args: object, **kwargs: object) -> object:
        """Decorate, build a class, or stand for the call's result — see the class."""
        if len(args) == 1 and not kwargs and _is_decorated(args[0]):
            if self._remembered is not None:
                return args[0]
            return StandIn(f"{self._path}()", unwrapped(args[0]))
        built = _class_built(args, kwargs)
        if built is not None:
            return built
        return StandIn(f"{self._path}()")

    def __getitem__(self, key: object) -> StandIn:
        """Return the stand-in for a subscription, such as a generic alias."""
        del key
        return StandIn(f"{self._path}[]")

    def __setitem__(self, key: object, value: object) -> None:
        """Let an item be set."""
        del key, value

    def __delitem__(self, key: object) -> None:
        """Let an item be deleted."""
        del key

    def __iter__(self) -> Iterator[object]:
        """Iterate over nothing."""
        return iter(())

    def __len__(self) -> int:
        """Hold nothing."""
        return 0

    def __contains__(self, item: object) -> bool:
        """Hold nothing."""
        del item
        return False

    def __bool__(self) -> bool:
        """Be something."""
        return True

    def __index__(self) -> int:
        """Be zero where a number is needed."""
        return 0

    def __int__(self) -> int:
        """Be zero where a number is needed."""
        return 0

    def __float__(self) -> float:
        """Be zero where a number is needed."""
        return 0.0

    def __round__(self, ndigits: int | None = None) -> int:
        """Be zero where a number is needed."""
        del ndigits
        return 0

    def __trunc__(self) -> int:
        """Be zero where a number is needed."""
        return 0

    def __floor__(self) -> int:
        """Be zero where a number is needed."""
        return 0

    def __ceil__(self) -> int:
        """Be zero where a number is needed."""
        return 0

    def __enter__(self) -> StandIn:
        """Be its own context."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Leave the context, raising nothing of its own."""
        del exc_info

    def __instancecheck__(self, instance: object) -> bool:
        """Have no instance: nothing is an instance of what is not installed."""
        del instance
        return False

    def __subclasscheck__(self, subclass: object) -> bool:
        """Have no subclass: nothing derives from what is not installed."""
        del subclass
        return False

    def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[type]:
        """Be derived from: as the remembered class where readable, else as a class of its own."""
        del bases
        if isinstance(self._remembered, type) and _readable(self._remembered):
            return (self._remembered,)
        base = self._base
        if base is None:
            module, _, name = self._path.rpartition(".")
            base = type(name or self._path, (_StandInBase,), {"__module__": module})
            setattr(base, STAND_IN_ATTRIBUTE, self._path)
            self._base = base
        return (base,)

    def _operation(self, *other: object) -> StandIn:
        del other
        return StandIn(f"{self._path}()")

    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = _operation
    __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = _operation
    __mod__ = __rmod__ = __pow__ = __rpow__ = __matmul__ = __rmatmul__ = _operation
    __and__ = __rand__ = __xor__ = __rxor__ = __lshift__ = __rshift__ = _operation
    __or__ = __ror__ = __neg__ = __pos__ = __abs__ = __invert__ = _operation
    __lt__ = __le__ = __gt__ = __ge__ = _operation

    @override
    def __repr__(self) -> str:
        return f"<stand-in for {self._path}>"


class _StandInBase:
    """What a class derived from a stand-in derives from; what it is subclassed with is let be."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        super().__init_subclass__()


def _is_decorated(obj: object) -> bool:
    """Whether ``obj`` is what a decorator is handed — or a stand-in remembering one."""
    return isinstance(unwrapped(obj), _DECORATED_TYPES)


def _readable(remembered: object) -> bool:
    """Whether a remembering stand-in may read ``remembered``: no truthfully loaded module's."""
    module = getattr(remembered, "__module__", None)
    return module == running_module() or module not in sys.modules


def _class_built(args: tuple[object, ...], kwargs: dict[str, object]) -> type | None:
    """Build the class a stand-in metaclass is called for — a name, bases, a namespace."""
    if len(args) != 3:  # noqa: PLR2004 — the three arguments a metaclass is called with
        return None
    name, bases, namespace = args
    if not (isinstance(name, str) and isinstance(bases, tuple) and isinstance(namespace, dict)):
        return None
    del kwargs
    # What a class statement hands its metaclass: a tuple of bases, a namespace of names.
    classes = tuple(base for base in cast("tuple[object, ...]", bases) if isinstance(base, type))
    return type(name, classes, dict(cast("dict[str, object]", namespace)))


def unwrapped(obj: object) -> object:
    """Return what a remembering stand-in remembers, and anything else as it is."""
    if isinstance(obj, StandIn):
        remembered = cast("object | None", object.__getattribute__(obj, "_remembered"))
        return remembered if remembered is not None else obj
    return obj


@final
class StandInModule(ModuleType):
    """A module of a package that is not installed: every name taken from it is a stand-in."""

    @override
    def __getattr__(self, name: str) -> StandIn:
        """Return the stand-in for ``name``; a dunder is answered as by any module without it."""
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return StandIn(f"{self.__name__}.{name}")


@final
class StandInFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Answers one inspection: stand-ins for packages not installed, set-aside modules as they are.

    Placed first: a set-aside module's own file would otherwise be found, and
    run again. It answers for nothing else — a package no other finder finds,
    being not installed, or a module set aside — and, on the thread that
    created it, only an import the inspected module's own code makes.
    Every other module whose body runs meanwhile imports truthfully: one
    probing for a missing package learns it is missing, and one needing it
    fails, which tells the scan to inspect that one first.

    One exception: a function of another module, called by the inspected
    body, is answered too — it imports for that body, which would fail
    without it. What it keeps of a stand-in, that module keeps:
    :attr:`lent_to` names it.

    What it serves is loaded only for the import statement asking for it:
    :meth:`sweep`, called before the next import, takes it out of
    ``sys.modules`` and off the packages it was set on, so no module run by
    that import finds it; :meth:`restore`, called once the inspected body has
    its hands back, puts it on its packages again, for the body to reach by
    a dotted name; :meth:`close` takes it off for good.

    A module of a set-aside package that is not set aside itself is never
    loaded under it: asked for one, the finder raises :class:`ChildOfSetAside`,
    for the inspection to inspect that module first.

    Attributes:
        packages_served: The packages not installed it stood in for.
        modules_served: The set-aside modules it gave back, in the order asked.
        lent_to: The modules whose functions, called by the inspected body,
            it answered.
    """

    def __init__(
        self,
        packages: frozenset[str],
        inspected: str,
        set_aside: Mapping[str, ModuleType],
    ) -> None:
        """Answer the inspection of ``inspected``.

        Args:
            packages: Top-level packages not installed, to stand in for.
            inspected: The module being inspected.
            set_aside: The modules set aside so far, to give back as they are.
        """
        self._packages = packages
        self._inspected = inspected
        self._set_aside = set_aside
        self._thread = threading.get_ident()
        self._served: dict[str, ModuleType] = {}
        self._attached: list[tuple[ModuleType, str, ModuleType]] = []
        self._own_records: dict[str, importlib.machinery.ModuleSpec | None] = {}
        self.packages_served: set[str] = set()
        self.modules_served: list[str] = []
        self.lent_to: set[str] = set()

    @override
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Answer for ``fullname`` with a stand-in or a set-aside module; ``None`` leaves it be."""
        del path, target
        if threading.get_ident() != self._thread:
            return None
        package = fullname.partition(".")[0]
        set_aside = self._set_aside.get(fullname)
        parent = fullname.rpartition(".")[0]
        if set_aside is None and package not in self._packages and parent not in self._set_aside:
            return None
        asking = importing_module()
        if asking != self._inspected:
            # Code naming no module, or another module's body, imports for itself.
            if asking is None or running_module() != self._inspected:
                return None
            self.lent_to.add(asking)
        if set_aside is None and package in self._packages:
            self.packages_served.add(package)
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        if set_aside is None:
            raise ChildOfSetAside(fullname, parent)
        if fullname not in self.modules_served:
            self.modules_served.append(fullname)
        return importlib.machinery.ModuleSpec(
            fullname, self, is_package=hasattr(set_aside, "__path__")
        )

    @override
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        """Return the set-aside module asked for, else a stand-in for it."""
        module = self._set_aside.get(spec.name)
        if module is None:
            return StandInModule(spec.name)
        # The import system gives a module the record it was found by; it gets its own back.
        _ = self._own_records.setdefault(spec.name, module.__spec__)
        return module

    @override
    def exec_module(self, module: ModuleType) -> None:
        """Record what was served, to take it away before the next import statement."""
        self._served[module.__name__] = module

    def sweep(self) -> None:
        """Take out of ``sys.modules``, and off its packages, all it served so far.

        Only this finder answers for those names, and it is swept before every
        import: nothing else can have put another module there. What it was
        set on the inspected module itself stays: that is what the module
        defines, and whatever reaches the module is set aside with it.
        """
        for name, module in self._served.items():
            parent, _, child = name.rpartition(".")
            holder = sys.modules.get(parent) if parent and parent != self._inspected else None
            if holder is not None and getattr(holder, child, None) is module:
                self._attached.append((holder, child, module))
        for name, module in self._served.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]
        self._served.clear()
        self._detach()

    def restore(self) -> None:
        """Put what it served back on its packages, where nothing else took its place."""
        for holder, child, module in self._attached:
            if child not in vars(holder):
                setattr(holder, child, module)

    def close(self) -> None:
        """Sweep, for good; give set-aside modules their own record back."""
        self.sweep()
        self._attached.clear()
        for name, record in self._own_records.items():
            self._set_aside[name].__spec__ = record
        self._own_records.clear()

    def _detach(self) -> None:
        for holder, child, module in reversed(self._attached):
            if vars(holder).get(child) is module:
                delattr(holder, child)


@final
class ChildOfSetAside(ImportError):  # noqa: N818 — a signal to the inspection, not an error
    """Raised to the inspection through the inspected body: a set-aside package's module is needed.

    Its package is set aside, so the module cannot be loaded truthfully
    there; the inspection inspects it first, and imports the body again.

    Attributes:
        child: The module asked for.
        parent: Its set-aside package.
    """

    def __init__(self, child: str, parent: str) -> None:
        """Signal that ``child``, of the set-aside ``parent``, must be inspected first."""
        super().__init__(f"{child!r} lies in the set-aside {parent!r}", name=child)
        self.child = child
        self.parent = parent
