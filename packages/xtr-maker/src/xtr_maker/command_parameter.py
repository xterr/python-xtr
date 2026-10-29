"""CommandParameter: one argument or option of a console command a maker writes."""

from __future__ import annotations

import builtins
import importlib
import keyword
import re
from dataclasses import dataclass
from enum import Enum
from typing import Final, final

from xtr_console.global_options import is_global_flag

from .exception import InvalidArgumentError
from .name_converter import NameConverter

__all__ = ["CommandParameter"]

LIST_TYPE: Final = "list[str]"
"""The one collection a parameter can hold: every value typed for it, as strings."""

SCALAR_TYPES: Final = ("str", "bool", "int", "float")
"""The types a parameter names by their own name; anything dotted is an enum class."""

_TYPE_ALIASES: Final = {"list": LIST_TYPE, LIST_TYPE: LIST_TYPE}
_IDENTIFIER: Final = re.compile(r"[a-z][a-z0-9_]*")
_DECLARATION: Final = re.compile(r"(?P<name>[^?:]*)(?P<optional>\?)?(?::(?P<type>.*))?")
_BUILTINS: Final = frozenset(dir(builtins))
_RESERVED: Final = {
    "io": "the command's output goes by that name",
    "self": "it names the command itself",
    "help": "it would take --help over",
    "version": "it would take --version over",
}


@final
@dataclass(frozen=True, slots=True)
class CommandParameter:
    """An argument — taken by position — or an option — taken as ``--name`` — of a command.

    Built with :meth:`parse` from what was typed on the command line
    (``recipient``, ``cc?:list``, ``limit:int``), or directly once each part is
    known; either way every part is checked, so a parameter that exists
    renders a signature the console accepts and the linter passes.

    Attributes:
        name: The parameter's name in the signature, a lowercase identifier.
        value_type: ``str``, ``bool``, ``int``, ``float``, ``list[str]``, or
            the dotted path of an ``Enum`` class, ``module.Class``.
        option: Whether the parameter is an option rather than an argument.
        required: Whether the command line must give it; options never are.
        description: The help text shown for it by ``--help``.

    Raises:
        InvalidArgumentError: When a part cannot be used.
    """

    name: str
    value_type: str
    option: bool = False
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """Refuse a part the console, the interpreter or the linter would not take."""
        _ = self.check_name(self.name, option=self.option)
        if self.value_type not in (*SCALAR_TYPES, LIST_TYPE):
            _check_enum(self.value_type)
        if self.option and self.required:
            raise InvalidArgumentError(f"Option {self.name!r} cannot be required: leave '?' out.")
        if not self.option and self.value_type == "bool":
            raise InvalidArgumentError(
                f"Argument {self.name!r} cannot be a bool: a flag is an option,"
                f" --option {self.name}."
            )
        if "\\" in self.description or '"""' in self.description:
            raise InvalidArgumentError(
                f"The help text of {self.name!r} cannot hold a backslash or three double quotes."
            )

    @classmethod
    def parse(cls, declaration: str, *, option: bool) -> CommandParameter:
        """Read ``name[?][:type]``: the name, ``?`` for an optional argument, then the type.

        The type defaults to ``str`` for an argument and ``bool`` for an
        option; ``list`` is ``list[str]``. The help text is made of the name's words.

        Raises:
            InvalidArgumentError: When a part cannot be used.
        """
        found = _DECLARATION.fullmatch(declaration.strip())
        if found is None:
            raise InvalidArgumentError(f"Cannot read {declaration!r} as name[?][:type].")
        name = cls.check_name(found["name"], option=option)
        if option and found["optional"]:
            raise InvalidArgumentError(f"Option {name!r} is never required: leave '?' out.")
        typed = found["type"]
        value_type = cls.check_type(typed if typed is not None else ("bool" if option else "str"))
        return cls(
            name,
            value_type,
            option=option,
            required=not option and not found["optional"],
            description=cls.default_description(name),
        )

    @staticmethod
    def check_name(typed: str, *, option: bool) -> str:
        """Return ``typed`` as the parameter's name, dashes made underscores.

        Raises:
            InvalidArgumentError: When the name is not a lowercase identifier,
                is a keyword, hides a builtin, or is one the console keeps.
        """
        name = typed.strip().replace("-", "_")
        kind = "an option" if option else "an argument"

        def refuse(reason: str) -> InvalidArgumentError:
            return InvalidArgumentError(f"{typed.strip()!r} cannot name {kind}: {reason}.")

        if _IDENTIFIER.fullmatch(name) is None:
            raise refuse("use lowercase letters, digits, '_' or '-', starting with a letter")
        if keyword.iskeyword(name):
            raise refuse("it is a Python keyword")
        reserved = _RESERVED.get(name)
        if reserved is not None:
            raise refuse(reserved)
        if name in _BUILTINS:
            raise refuse("it would hide the builtin of the same name")
        flag = f"--{NameConverter.as_kebab_case(name)}"
        if option and is_global_flag(flag):
            raise refuse(f"every command already takes {flag}")
        return name

    @staticmethod
    def check_type(typed: str) -> str:
        """Return ``typed`` as a value type: ``list`` is ``list[str]``; dotted is an enum class.

        Raises:
            InvalidArgumentError: When ``typed`` is none of the types, or names
                no importable ``Enum`` class.
        """
        value_type = _TYPE_ALIASES.get(typed.strip(), typed.strip())
        if value_type in (*SCALAR_TYPES, LIST_TYPE):
            return value_type
        if "." not in value_type:
            raise InvalidArgumentError(
                f"There is no type {typed!r}; use {', '.join(SCALAR_TYPES)}, list,"
                " or an enum class as module.Class."
            )
        _check_enum(value_type)
        return value_type

    @staticmethod
    def default_description(name: str) -> str:
        """Return the help text made of ``name``'s words: ``dry_run`` → ``Dry run.``."""
        return f"{' '.join(NameConverter.words(name)).capitalize()}."

    @property
    def enum_class(self) -> tuple[str, str] | None:
        """The module and class name of the enum it holds; ``None`` for any other type."""
        if self.value_type in (*SCALAR_TYPES, LIST_TYPE):
            return None
        module, _, class_name = self.value_type.rpartition(".")
        return module, class_name

    @property
    def is_list(self) -> bool:
        """Whether it collects every value typed for it."""
        return self.value_type == LIST_TYPE

    def declaration(self, type_name: str) -> str:
        """Return the parameter as the signature spells it, its type written ``type_name``.

        A required argument has no default; anything else may be left out: a
        flag is then ``False``, any other value ``None``.
        """
        if self.option and self.value_type == "bool":
            return f"{self.name}: bool = False"
        if self.required:
            return f"{self.name}: {type_name}"
        return f"{self.name}: {type_name} | None = None"


def _check_enum(path: str) -> None:
    """Refuse a dotted path that does not import an ``Enum`` class.

    Raises:
        InvalidArgumentError: When the module does not import, has no such
            name, or the name is not an ``Enum`` class.
    """
    module_name, _, class_name = path.rpartition(".")
    if not module_name or not class_name.isidentifier():
        raise InvalidArgumentError(f"Name the enum class as module.Class, not {path!r}.")
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise InvalidArgumentError(
            f"Cannot import {module_name!r} for {path!r}: {error}"
        ) from error
    found: object = getattr(module, class_name, None)
    if not (isinstance(found, type) and issubclass(found, Enum)):
        raise InvalidArgumentError(f"{path!r} is not an Enum class.")
