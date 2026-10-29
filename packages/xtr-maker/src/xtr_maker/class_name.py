"""ClassName: what a person typed, as the class, module and file a maker writes."""

from __future__ import annotations

import builtins
import keyword
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, final

from .exception import InvalidClassNameError
from .name_converter import NameConverter

__all__ = ["ClassName"]

_TYPED: Final = re.compile(r"[A-Za-z0-9_ ./-]+")
"""What a typed name may hold: words, and the separators between them and their packages."""

_PACKAGE_SEPARATOR: Final = re.compile(r"[./]")

_BUILTINS: Final = frozenset(dir(builtins))


@final
@dataclass(frozen=True, slots=True)
class ClassName:
    """A class a maker writes: its name, the package it lives in, and its file.

    Built with :meth:`create` from what a person typed; built directly, every
    part is checked the same way. The package is the folder for the kind of
    class (``message_handler``) under the application package, plus the
    subpackages the person typed before the name (``ordering.PlaceOrder``)::

        name = ClassName.create(
            "ordering.place order", root_package="app", kind="message_handler", suffix="Handler"
        )
        name.short_name  # "PlaceOrderHandler"
        name.module  # "app.message_handler.ordering.place_order_handler"
        name.path  # PurePosixPath("message_handler/ordering/place_order_handler.py")

    Attributes:
        root_package: The application package, dotted.
        package: The package under it, one entry per folder.
        short_name: The class's own name.
        suffix: The ending every class of its kind carries, ``""`` for none.

    Raises:
        InvalidClassNameError: When the class name is not an identifier, is a
            keyword, or shadows a builtin, or a package part is not an
            identifier or is a keyword.
    """

    root_package: str
    package: tuple[str, ...]
    short_name: str
    suffix: str = ""

    def __post_init__(self) -> None:
        """Refuse any part that would not import, or would hide a name the code relies on."""
        _check_class(self.short_name)
        for part in (*self.root_package.split("."), *self.package, self.snake_name):
            _check_module(part, self.short_name)

    @classmethod
    def create(cls, name: str, *, root_package: str, kind: str, suffix: str = "") -> ClassName:
        """Resolve what a person typed into the class a maker writes.

        Args:
            name: The class name as typed — ``place order``, ``PlaceOrder`` —
                optionally after subpackages, separated by ``.`` or ``/``:
                ``ordering.PlaceOrder`` puts the class in ``<kind>/ordering/``.
            root_package: The application package, dotted.
            kind: The folder for the kind of class, dotted when nested
                (``security.voter``).
            suffix: The ending every class of its kind carries; added unless
                the name already ends with it.

        Returns:
            The class, its package and its suffix.

        Raises:
            InvalidClassNameError: When ``name`` is empty, holds a character no
                name can, or resolves to a part :class:`ClassName` refuses.
        """
        typed = name.strip()
        if not typed or _TYPED.fullmatch(typed) is None:
            raise InvalidClassNameError(
                name, "use letters, digits, spaces, '_' or '-', and '.' before a subpackage"
            )
        *subpackages, last = _PACKAGE_SEPARATOR.split(typed)
        short_name = NameConverter.as_class_name(last)
        if suffix and not short_name.endswith(suffix):
            short_name += suffix
        package = (
            *kind.split("."),
            *(NameConverter.as_snake_case(part) for part in subpackages),
        )
        return cls(root_package=root_package, package=package, short_name=short_name, suffix=suffix)

    @property
    def name_without_suffix(self) -> str:
        """The class name without its kind's suffix: ``PlaceOrderHandler`` → ``PlaceOrder``."""
        if self.suffix and self.short_name != self.suffix:
            return self.short_name.removesuffix(self.suffix)
        return self.short_name

    @property
    def snake_name(self) -> str:
        """The module's own name: ``PlaceOrderHandler`` → ``place_order_handler``."""
        return NameConverter.as_snake_case(self.short_name)

    @property
    def package_name(self) -> str:
        """The dotted package the module lives in."""
        return ".".join((self.root_package, *self.package))

    @property
    def module(self) -> str:
        """The dotted module the class is imported from."""
        return f"{self.package_name}.{self.snake_name}"

    @property
    def path(self) -> PurePosixPath:
        """The module's file, relative to the application package's directory."""
        return PurePosixPath(*self.package, f"{self.snake_name}.py")


def _check_class(short_name: str) -> None:
    """Refuse a class name that does not parse, or that hides a builtin."""
    if not short_name.isidentifier():
        raise InvalidClassNameError(short_name, "it is not a Python identifier")
    if keyword.iskeyword(short_name) or keyword.issoftkeyword(short_name):
        raise InvalidClassNameError(short_name, "it is a Python keyword")
    if short_name in _BUILTINS:
        raise InvalidClassNameError(short_name, "it would hide the builtin of the same name")


def _check_module(part: str, short_name: str) -> None:
    """Refuse a package or module name an import statement cannot spell."""
    if not part.isidentifier():
        raise InvalidClassNameError(short_name, f"module {part!r} is not a Python identifier")
    if keyword.iskeyword(part):
        raise InvalidClassNameError(short_name, f"module {part!r} is a Python keyword")
