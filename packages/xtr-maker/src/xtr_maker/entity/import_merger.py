"""ImportMerger: the imports a change needs, merged into a module as the linter sorts them."""

from __future__ import annotations

import re
import sys
from enum import IntEnum
from typing import TYPE_CHECKING, Final, final

import libcst as cst
from libcst.helpers import get_full_name_for_node

from .needed_import import NeededImport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_maker.import_collector import ImportCollector

__all__ = ["ImportMerger"]

_INDENT: Final = "    "
_DIGITS: Final = re.compile(r"(\d+)")
_BLANK: Final = (cst.EmptyLine(indent=False),)
"""One blank line, with no trailing indentation inside a block."""

_Natural = tuple[tuple[int, int, str], ...]
_Key = tuple[int, int, tuple[_Natural, _Natural]]


class _Section(IntEnum):
    FUTURE = 0
    STANDARD_LIBRARY = 1
    THIRD_PARTY = 2
    FIRST_PARTY = 3


_TYPE_CHECKING: Final = NeededImport("typing", "TYPE_CHECKING")
"""What the ``if TYPE_CHECKING:`` block needs imported, and only when it holds something."""


@final
class ImportMerger:
    """Adds the imports an :class:`~xtr_maker.ImportCollector` holds to an existing module.

    A name already imported is left alone. A name from a module the file
    already imports from joins that statement, the names re-sorted; any other
    gets a statement of its own, placed where the linter's import sorting
    would put it — standard library, third-party, then the application's own
    package, a blank line between them — so the file needs no fixing. Names
    used only in annotations go in the ``if TYPE_CHECKING:`` block, which is
    written after the imports when the file has none.

    Every statement it does not touch keeps its exact text. A statement
    holding a comment is never rewritten: a name it would have joined gets a
    statement of its own instead.
    """

    __slots__ = ("_first_party", "_line_length")

    def __init__(self, first_party: str, *, line_length: int = 88) -> None:
        """Merge into modules of the application package ``first_party``.

        Args:
            first_party: The application's root package; its imports are grouped last.
            line_length: Longest line a statement is written on before it is wrapped.
        """
        self._first_party = first_party.split(".", 1)[0]
        self._line_length = line_length

    def merge(self, module: cst.Module, imports: ImportCollector) -> cst.Module:
        """Return ``module`` with every import of ``imports`` it lacks."""
        runtime, annotations = NeededImport.read(imports.render())
        runtime = [needed for needed in runtime if needed != _TYPE_CHECKING]
        body: list[cst.BaseStatement] = list(module.body)
        start, end = _import_region(body)
        body = self._merge_block(body, (start, end), runtime, 0)
        _, end = _import_region(body)
        present = body[start:end]
        annotations = [needed for needed in annotations if not needed.is_in(present)]
        if annotations:
            body = self._merge_block(body, (start, end), [_TYPE_CHECKING], 0)
            _, end = _import_region(body)
            body = self._merge_type_checking(body, end, annotations)
        return module.with_changes(body=body)

    def _merge_type_checking(
        self, body: list[cst.BaseStatement], end: int, needed: Sequence[NeededImport]
    ) -> list[cst.BaseStatement]:
        """Merge ``needed`` into the ``if TYPE_CHECKING:`` block, writing one at ``end`` if none."""
        for index, block in enumerate(body):
            if (
                isinstance(block, cst.If)
                and isinstance(block.body, cst.IndentedBlock)
                and _is_type_checking(block)
            ):
                suite = block.body
                inner = list(suite.body)
                merged = self._merge_block(inner, (0, len(inner)), needed, len(_INDENT))
                body[index] = block.with_changes(body=suite.with_changes(body=merged))
                return body
        inner = self._merge_block([], (0, 0), needed, len(_INDENT))
        statement = cst.If(
            test=cst.Name("TYPE_CHECKING"),
            body=cst.IndentedBlock(body=inner),
            leading_lines=_BLANK,
        )
        body.insert(end, statement)
        _ensure_blank_before(body, end + 1)
        return body

    def _merge_block(
        self,
        statements: list[cst.BaseStatement],
        region: tuple[int, int],
        needed: Sequence[NeededImport],
        indent: int,
    ) -> list[cst.BaseStatement]:
        """Merge ``needed`` into the import statements ``statements[start:end]``."""
        start, end = region
        for name in needed:
            current = statements[start:end]
            if name.is_in(current):
                continue
            joined = name.joinable(current)
            if joined is not None:
                index, names = joined
                rebuilt = self._statement(name.module, [*names, (name.name, None)], indent)
                statements[start + index] = rebuilt.with_changes(
                    leading_lines=_leading(current[index])
                )
                continue
            key = (self._section(name.module), 1, _natural_key(name.module))
            position = start + next(
                (index for index, found in enumerate(current) if self._key(found) > key),
                len(current),
            )
            first = statements[position] if position < end else None
            statement = self._statement(name.module, [(name.name, name.asname)], indent)
            if position == start:
                lines = _leading(first) if first is not None else _opening(start)
                statement = statement.with_changes(leading_lines=lines)
            statements.insert(position, statement)
            end += 1
            for index in (position, position + 1):
                if start < index < end:
                    statements[index] = self._spaced(statements[index], statements[index - 1])
            if first is None and position == start:
                _ensure_blank_before(statements, end)
        return statements

    def _spaced(
        self, statement: cst.BaseStatement, previous: cst.BaseStatement
    ) -> cst.BaseStatement:
        """Return ``statement`` with a blank line before it exactly when it starts a section."""
        lines = _leading(statement)
        if any(line.comment is not None for line in lines):
            return statement
        starts_section = self._key(statement)[0] != self._key(previous)[0]
        if bool(lines) == starts_section:
            return statement
        return statement.with_changes(leading_lines=_BLANK if starts_section else ())

    def _statement(
        self, module: str, names: list[tuple[str, str | None]], indent: int
    ) -> cst.BaseStatement:
        """Return ``from module import names``, sorted, wrapped one per line when too long."""
        texts = [
            name if asname is None else f"{name} as {asname}"
            for name, asname in sorted(names, key=_member_key)
        ]
        line = f"from {module} import {', '.join(texts)}"
        if indent + len(line) <= self._line_length:
            return cst.parse_statement(f"{line}\n")
        wrapped = "".join(f"{_INDENT}{text},\n" for text in texts)
        return cst.parse_statement(f"from {module} import (\n{wrapped})\n")

    def _key(self, statement: cst.BaseStatement) -> _Key:
        """Order ``import x`` before ``from x import``, within the section of ``x``."""
        module = NeededImport.module_of(statement) or self._first_party
        plain = isinstance(statement, cst.SimpleStatementLine) and isinstance(
            statement.body[0], cst.Import
        )
        return (self._section(module), 0 if plain else 1, _natural_key(module))

    def _section(self, module: str) -> _Section:
        top = module.split(".", 1)[0]
        if module == "__future__":
            return _Section.FUTURE
        if top == self._first_party or module.startswith("."):
            return _Section.FIRST_PARTY
        if top in sys.stdlib_module_names:
            return _Section.STANDARD_LIBRARY
        return _Section.THIRD_PARTY


def _import_region(body: Sequence[cst.BaseStatement]) -> tuple[int, int]:
    """Return where the module's leading import statements start and end, after its docstring."""
    start = 1 if body and _is_docstring(body[0]) else 0
    end = start
    while end < len(body) and _is_import(body[end]):
        end += 1
    return start, end


def _is_docstring(statement: cst.BaseStatement) -> bool:
    if not isinstance(statement, cst.SimpleStatementLine):
        return False
    first = statement.body[0]
    return isinstance(first, cst.Expr) and isinstance(
        first.value, cst.SimpleString | cst.ConcatenatedString
    )


def _is_import(statement: cst.BaseStatement) -> bool:
    return isinstance(statement, cst.SimpleStatementLine) and all(
        isinstance(part, cst.Import | cst.ImportFrom) for part in statement.body
    )


def _is_type_checking(statement: cst.If) -> bool:
    if statement.orelse is not None:
        return False
    name = get_full_name_for_node(statement.test)
    return name is not None and name.rsplit(".", 1)[-1] == "TYPE_CHECKING"


def _ensure_blank_before(statements: list[cst.BaseStatement], index: int) -> None:
    """Give the statement at ``index``, if any, a blank line before it when it has none."""
    if index < len(statements) and not _leading(statements[index]):
        statements[index] = statements[index].with_changes(leading_lines=_BLANK)


def _leading(statement: cst.BaseStatement) -> Sequence[cst.EmptyLine]:
    """Return the blank and comment lines before ``statement``."""
    if isinstance(statement, cst.SimpleStatementLine | cst.BaseCompoundStatement):
        return statement.leading_lines
    return ()


def _opening(start: int) -> tuple[cst.EmptyLine, ...]:
    """Return the lines before a first import: a blank one after a docstring, none at the top."""
    return _BLANK if start > 0 else ()


def _natural(text: str) -> _Natural:
    """Return a key ordering ``item2`` before ``item10``, the way the sorter does."""
    return tuple(
        (0, int(chunk), "") if chunk.isdigit() else (1, 0, chunk)
        for chunk in _DIGITS.split(text)
        if chunk
    )


def _natural_key(module: str) -> tuple[_Natural, _Natural]:
    return (_natural(module.lower()), _natural(module))


def _member_key(member: tuple[str, str | None]) -> tuple[int, _Natural, _Natural, str]:
    """Order constants first, then classes, then everything else, case-insensitively."""
    name, asname = member
    if len(name) > 1 and name.isupper():
        rank = 0
    elif name[0].isupper():
        rank = 1
    else:
        rank = 2
    return (rank, _natural(name.lower()), _natural(name), asname or "")
