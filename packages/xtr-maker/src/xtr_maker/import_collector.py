"""ImportCollector: the imports a generated module needs, written the way the linter sorts them."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Final, final

from .name_converter import NameConverter

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["ImportCollector"]

_DEFAULT_LINE_LENGTH: Final = 88
"""The formatter's default line length: an import longer than this is wrapped."""

_INDENT: Final = "    "
_DIGITS: Final = re.compile(r"(\d+)")


class _Section(IntEnum):
    """The groups imports are written in, in this order, a blank line between them."""

    STANDARD_LIBRARY = 0
    THIRD_PARTY = 1
    FIRST_PARTY = 2


@dataclass(slots=True)
class _Import:
    """One imported name, the name it is bound to, and whether code reads it at runtime."""

    module: str
    name: str
    alias: str | None
    runtime: bool

    @property
    def bound(self) -> str:
        return self.alias if self.alias is not None else self.name

    @property
    def text(self) -> str:
        return self.name if self.alias is None else f"{self.name} as {self.alias}"


@final
class ImportCollector:
    """Collects ``from module import Name`` imports and renders them sorted and grouped.

    Makers never write an import by hand in a template: they add what the code
    uses here and place :meth:`render` where the imports go, after the
    template's own ``from __future__ import annotations``. The output is what
    the linter's import sorting writes with its defaults — standard library,
    third-party, then the application's own package, a blank line between
    them; one statement per module, names ordered constants, classes, then the
    rest; a statement too long for one line wrapped with a trailing comma — so
    a generated file needs no fixing.

    A name added only for annotations goes in an ``if TYPE_CHECKING:`` block,
    which is written after the rest with ``TYPE_CHECKING`` imported for it. Two
    modules exporting the same name get the second one an alias; :meth:`add`
    returns the name the code must use.
    """

    __slots__ = ("_bound", "_first_party", "_imports", "_line_length")

    def __init__(self, first_party: str, *, line_length: int = _DEFAULT_LINE_LENGTH) -> None:
        """Collect imports for a module of the application package ``first_party``.

        Args:
            first_party: The application's root package; imports from it are
                grouped last.
            line_length: Longest line a statement is written on before it is
                wrapped.
        """
        self._first_party = first_party.split(".", 1)[0]
        self._line_length = line_length
        self._imports: dict[tuple[str, str], _Import] = {}
        self._bound: set[str] = set()

    def add(self, module: str, name: str, *, type_checking: bool = False) -> str:
        """Import ``name`` from ``module``, and return the name the code refers to it by.

        Args:
            module: The dotted module to import from.
            name: The name to import.
            type_checking: Whether the code uses the name in annotations only;
                a name added both ways is imported at runtime.

        Returns:
            ``name``, or the alias it was given because another module's name
            already holds it.
        """
        found = self._imports.get((module, name))
        if found is not None:
            found.runtime = found.runtime or not type_checking
            return found.bound
        alias = self._alias(module, name) if name in self._bound else None
        added = _Import(module, name, alias, runtime=not type_checking)
        self._imports[module, name] = added
        self._bound.add(added.bound)
        return added.bound

    def render(self) -> str:
        """Return the import statements, without a trailing newline; ``""`` when there are none."""
        runtime = [found for found in self._imports.values() if found.runtime]
        annotations = [found for found in self._imports.values() if not found.runtime]
        if annotations and ("typing", "TYPE_CHECKING") not in self._imports:
            runtime.append(_Import("typing", "TYPE_CHECKING", None, runtime=True))
        blocks = [self._sections(runtime, "")] if runtime else []
        if annotations:
            blocks.append(f"if TYPE_CHECKING:\n{self._sections(annotations, _INDENT)}")
        return "\n\n".join(blocks)

    def _alias(self, module: str, name: str) -> str:
        """Return a free name for ``name``, prefixed with the last part of its module naming more.

        ``Event`` from ``xtr_messenger.event`` becomes ``XtrMessengerEvent``: the
        ``event`` module repeats the name, so the package above it tells the two apart.
        """
        own = NameConverter.as_snake_case(name)
        parts = module.split(".")
        last = next((part for part in reversed(parts) if part != own), parts[-1])
        if name[0].isupper():
            base = f"{NameConverter.as_class_name(last)}{name}"
        else:
            base = f"{NameConverter.as_snake_case(last)}_{name}"
        alias, counter = base, 2
        while alias in self._bound:
            alias, counter = f"{base}{counter}", counter + 1
        return alias

    def _sections(self, imports: Iterable[_Import], indent: str) -> str:
        """Return ``imports`` as statements, grouped by section, each group sorted."""
        grouped: dict[_Section, list[_Import]] = {}
        for found in imports:
            grouped.setdefault(self._section(found.module), []).append(found)
        return "\n\n".join(
            "\n".join(self._statements(grouped[section], indent)) for section in sorted(grouped)
        )

    def _statements(self, imports: list[_Import], indent: str) -> list[str]:
        """Return one statement per module for plain names, and one per aliased name, sorted."""
        merged: dict[str, list[_Import]] = {}
        statements: list[tuple[str, list[_Import]]] = []
        for found in imports:
            if found.alias is None:
                merged.setdefault(found.module, []).append(found)
            else:
                statements.append((found.module, [found]))
        statements.extend(merged.items())
        ordered = [(module, sorted(members, key=_member_key)) for module, members in statements]
        ordered.sort(
            key=lambda statement: (_module_key(statement[0]), _member_key(statement[1][0]))
        )
        return [self._statement(module, members, indent) for module, members in ordered]

    def _statement(self, module: str, members: list[_Import], indent: str) -> str:
        """Return one ``from`` statement, wrapped one name per line when too long."""
        line = f"{indent}from {module} import {', '.join(member.text for member in members)}"
        if len(line) <= self._line_length:
            return line
        names = "".join(f"{indent}{_INDENT}{member.text},\n" for member in members)
        return f"{indent}from {module} import (\n{names}{indent})"

    def _section(self, module: str) -> _Section:
        top = module.split(".", 1)[0]
        if top == self._first_party:
            return _Section.FIRST_PARTY
        if top in sys.stdlib_module_names:
            return _Section.STANDARD_LIBRARY
        return _Section.THIRD_PARTY


def _natural(text: str) -> tuple[tuple[int, int, str], ...]:
    """Return a key ordering ``item2`` before ``item10``, the way the sorter does."""
    return tuple(
        (0, int(chunk), "") if chunk.isdigit() else (1, 0, chunk)
        for chunk in _DIGITS.split(text)
        if chunk
    )


def _module_key(module: str) -> tuple[object, ...]:
    return (_natural(module.lower()), _natural(module))


def _member_key(member: _Import) -> tuple[object, ...]:
    """Order constants first, then classes, then everything else, case-insensitively."""
    name = member.name
    if len(name) > 1 and name.isupper():
        rank = 0
    elif name[0].isupper():
        rank = 1
    else:
        rank = 2
    return (rank, _natural(name.lower()), _natural(name), member.alias or "")
