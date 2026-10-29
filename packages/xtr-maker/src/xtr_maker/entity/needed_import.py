"""NeededImport: one name a change uses, and where a module's statements already import it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import libcst as cst
from libcst.helpers import get_full_name_for_node

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["NeededImport"]


@final
@dataclass(frozen=True, slots=True)
class NeededImport:
    """``from module import name [as asname]``, as a change needs it.

    Attributes:
        module: The dotted module imported from.
        name: The name imported.
        asname: The name it is bound to, when not its own.
    """

    module: str
    name: str
    asname: str | None = None

    @classmethod
    def read(cls, rendered: str) -> tuple[list[NeededImport], list[NeededImport]]:
        """Return the runtime imports, then the annotation-only ones, of rendered import code.

        ``rendered`` is what :meth:`~xtr_maker.ImportCollector.render` returns:
        ``from`` statements, then an ``if TYPE_CHECKING:`` block.
        """
        runtime: list[NeededImport] = []
        annotations: list[NeededImport] = []
        for statement in cst.parse_module(rendered).body:
            lines: Sequence[cst.BaseStatement] = (statement,)
            target = runtime
            if isinstance(statement, cst.If) and isinstance(statement.body, cst.IndentedBlock):
                lines, target = statement.body.body, annotations
            for line in lines:
                node = _import_from(line)
                if node is None or isinstance(node.names, cst.ImportStar):
                    continue
                module = _full_name(node.module)
                target.extend(
                    cls(module, _full_name(alias.name), _asname(alias)) for alias in node.names
                )
        return runtime, annotations

    @staticmethod
    def module_of(statement: cst.BaseStatement) -> str | None:
        """Return the module an import statement imports from — ``.x`` when relative.

        ``None`` for a statement that is no import.
        """
        node = _import_from(statement)
        if node is not None:
            return "." * len(node.relative) + _full_name(node.module)
        if isinstance(statement, cst.SimpleStatementLine):
            first = statement.body[0]
            if isinstance(first, cst.Import):
                return _full_name(first.names[0].name)
        return None

    def is_in(self, statements: Sequence[cst.BaseStatement]) -> bool:
        """Report whether one of ``statements`` already imports this name, bound the same."""
        for names in _absolute_imports(statements, self.module).values():
            if (self.name, self.asname) in names:
                return True
        return False

    def joinable(
        self, statements: Sequence[cst.BaseStatement]
    ) -> tuple[int, list[tuple[str, str | None]]] | None:
        """Return the comment-free statement importing from this module, and its names.

        A name bound under another name gets a statement of its own, so it has none.
        """
        if self.asname is not None:
            return None
        for index, names in _absolute_imports(statements, self.module).items():
            if "#" not in cst.Module([]).code_for_node(statements[index]):
                return index, names
        return None


def _absolute_imports(
    statements: Sequence[cst.BaseStatement], module: str
) -> dict[int, list[tuple[str, str | None]]]:
    """Return, by index, the names each ``from module import`` among ``statements`` imports."""
    found: dict[int, list[tuple[str, str | None]]] = {}
    for index, statement in enumerate(statements):
        node = _import_from(statement)
        if node is None or node.relative or isinstance(node.names, cst.ImportStar):
            continue
        if _full_name(node.module) == module:
            found[index] = [(_full_name(alias.name), _asname(alias)) for alias in node.names]
    return found


def _import_from(statement: cst.BaseStatement) -> cst.ImportFrom | None:
    if not isinstance(statement, cst.SimpleStatementLine) or len(statement.body) != 1:
        return None
    node = statement.body[0]
    return node if isinstance(node, cst.ImportFrom) else None


def _full_name(node: cst.BaseExpression | None) -> str:
    return (get_full_name_for_node(node) if node is not None else None) or ""


def _asname(alias: cst.ImportAlias) -> str | None:
    if alias.asname is None:
        return None
    return _full_name(alias.asname.name)
