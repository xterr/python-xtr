"""EntitySourceEditor: an entity module's source, with mapped attributes added to its class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import libcst as cst
from libcst.helpers import get_full_name_for_node

from xtr_maker.exception import InvalidArgumentError
from xtr_maker.import_collector import ImportCollector

from .import_merger import ImportMerger
from .needed_import import NeededImport

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from xtr_maker.class_name import ClassName

    from .mapped_attribute import MappedAttribute

__all__ = ["EntitySourceEditor"]

_CYCLES_ALLOWED: Final = "# pyright: reportImportCycles=false"
_CYCLES_REASON: Final = "# The entities imported here may import this one back, for type checking."


@final
class EntitySourceEditor:
    """Adds attributes to an entity class, and the imports they need, leaving the rest as it was.

    The source is parsed into a concrete syntax tree, which keeps every
    character — comments, blank lines, quotes — so a file read and written
    back unchanged is byte-identical, and an addition changes only the lines
    it adds and the import lines it needs.

    An attribute goes after the class's last ``Mapped`` one, or, when it has
    none, after its docstring and ``__tablename__``. A name the class already
    has is refused.

    An attribute naming another of the application's entities imports it
    under ``if TYPE_CHECKING:``. When the other entity names this one back,
    the two modules import each other: nothing runs that cycle, but a type
    checker reporting import cycles would, so the block is preceded by the
    comment telling it not to.
    """

    __slots__ = ("_entity", "_line_length", "_merger", "_module", "_names")

    def __init__(self, source: str, entity: ClassName, *, line_length: int = 88) -> None:
        """Edit ``source``, the module defining ``entity``.

        Args:
            source: The module's text.
            entity: The entity class, and the module it lives in.
            line_length: Longest line an added statement is written on.

        Raises:
            InvalidArgumentError: When the source does not parse, or defines no
                class named after the entity.
        """
        try:
            self._module = cst.parse_module(source)
        except cst.ParserSyntaxError as error:
            raise InvalidArgumentError(
                f"{entity.path} does not parse, so {entity.short_name} cannot be edited: {error}"
            ) from None
        self._entity = entity
        self._line_length = line_length
        self._merger = ImportMerger(entity.root_package, line_length=line_length)
        self._names = set(_class_names(self._class()[1]))

    @property
    def entity(self) -> ClassName:
        """The entity class, and the module it lives in."""
        return self._entity

    @property
    def source(self) -> str:
        """The module's text, every addition so far included."""
        return self._module.code

    @property
    def bases(self) -> tuple[str, ...]:
        """The class's bases, as written: ``("UUIDAuditBase",)``."""
        return tuple(_full_name(argument.value) for argument in self._class()[1].bases)

    @property
    def table_name(self) -> str | None:
        """The ``__tablename__`` the class declares, when it is a plain string."""
        for statement in _body(self._class()[1]):
            for node in _small(statement):
                if (
                    isinstance(node, cst.Assign)
                    and _assigned(node) == ["__tablename__"]
                    and isinstance(node.value, cst.SimpleString)
                ):
                    value = node.value.evaluated_value
                    return value if isinstance(value, str) else None
        return None

    def has_attribute(self, name: str) -> bool:
        """Report whether the class already defines ``name``."""
        return name in self._names

    def imports(self) -> ImportCollector:
        """Return an empty collector for what the next attribute uses."""
        return ImportCollector(self._entity.root_package, line_length=self._line_length)

    def add_attribute(self, attribute: MappedAttribute, imports: ImportCollector) -> None:
        """Add ``attribute`` to the class, and ``imports`` to the module.

        Raises:
            InvalidArgumentError: When the class already defines the name.
        """
        if attribute.name in self._names:
            raise InvalidArgumentError(
                f"{self._entity.short_name} already has a property {attribute.name!r}."
            )
        index, definition = self._class()
        block = definition.body
        if not isinstance(block, cst.IndentedBlock):
            raise InvalidArgumentError(
                f"{self._entity.short_name} is defined on one line; give it a body first."
            )
        width = len(block.indent if block.indent is not None else self._module.default_indent)
        text = attribute.render(indent=width, line_length=self._line_length)
        statement = cst.parse_statement(text, config=self._module.config_for_parsing)
        statements = list(block.body)
        position, after_mapped = _insertion_point(statements)
        if not after_mapped and position > 0:
            statement = statement.with_changes(leading_lines=(cst.EmptyLine(indent=False),))
        statements.insert(position, statement)
        body = list(self._module.body)
        body[index] = definition.with_changes(body=block.with_changes(body=statements))
        self._module = self._merger.merge(self._module.with_changes(body=body), imports)
        if self._imports_an_entity(imports):
            self._module = _allow_import_cycles(self._module)
        self._names.add(attribute.name)

    def _imports_an_entity(self, imports: ImportCollector) -> bool:
        """Report whether ``imports`` names a module of the application for annotations only."""
        root = self._entity.root_package.split(".", 1)[0]
        _, annotations = NeededImport.read(imports.render())
        return any(needed.module.split(".", 1)[0] == root for needed in annotations)

    def _class(self) -> tuple[int, cst.ClassDef]:
        """Return the entity class and its index among the module's statements.

        Raises:
            InvalidArgumentError: When the module defines no such class.
        """
        for index, statement in enumerate(self._module.body):
            if isinstance(statement, cst.ClassDef) and statement.name.value == (
                self._entity.short_name
            ):
                return index, statement
        raise InvalidArgumentError(
            f"{self._entity.path} defines no class {self._entity.short_name}."
        )


def _allow_import_cycles(module: cst.Module) -> cst.Module:
    """Return ``module`` with the import-cycle comment before its ``if TYPE_CHECKING:`` block.

    Left as it is when the comment is anywhere in the module already.
    """
    if _CYCLES_ALLOWED in module.code:
        return module
    body = list(module.body)
    for index, statement in enumerate(body):
        if isinstance(statement, cst.If) and _full_name(statement.test).endswith("TYPE_CHECKING"):
            comments = tuple(
                cst.EmptyLine(indent=False, comment=cst.Comment(text))
                for text in (_CYCLES_REASON, _CYCLES_ALLOWED)
            )
            body[index] = statement.with_changes(
                leading_lines=(*statement.leading_lines, *comments)
            )
            return module.with_changes(body=body)
    return module


def _insertion_point(statements: Sequence[cst.BaseStatement]) -> tuple[int, bool]:
    """Return where a new attribute goes, and whether it follows a ``Mapped`` one.

    After the last ``Mapped`` attribute — and the docstring right after it,
    if any — or else after the class's leading docstring and dunder settings.
    """
    last = None
    for index, statement in enumerate(statements):
        if any(_is_mapped(node) for node in _small(statement)):
            last = index
    if last is not None:
        following = last + 1
        if following < len(statements) and _is_docstring(statements[following]):
            following += 1
        return following, True
    position = 0
    while position < len(statements) and _is_header(statements[position], position):
        position += 1
    return position, False


def _is_header(statement: cst.BaseStatement, index: int) -> bool:
    if index == 0 and _is_docstring(statement):
        return True
    return any(
        isinstance(node, cst.Assign | cst.AnnAssign)
        and all(name.startswith("__") for name in _assigned(node))
        and bool(_assigned(node))
        for node in _small(statement)
    )


def _is_mapped(node: cst.BaseSmallStatement) -> bool:
    if not isinstance(node, cst.AnnAssign):
        return False
    annotation = node.annotation.annotation
    if not isinstance(annotation, cst.Subscript):
        return False
    return _full_name(annotation.value).rsplit(".", 1)[-1] == "Mapped"


def _is_docstring(statement: cst.BaseStatement) -> bool:
    nodes = _small(statement)
    return (
        len(nodes) == 1
        and isinstance(nodes[0], cst.Expr)
        and isinstance(nodes[0].value, cst.SimpleString | cst.ConcatenatedString)
    )


def _class_names(definition: cst.ClassDef) -> Iterator[str]:
    """Yield every name the class body binds: attributes, methods, nested classes."""
    for statement in _body(definition):
        if isinstance(statement, cst.FunctionDef | cst.ClassDef):
            yield statement.name.value
        for node in _small(statement):
            if isinstance(node, cst.Assign | cst.AnnAssign):
                yield from _assigned(node)


def _assigned(node: cst.Assign | cst.AnnAssign) -> list[str]:
    targets = [node.target] if isinstance(node, cst.AnnAssign) else [t.target for t in node.targets]
    return [target.value for target in targets if isinstance(target, cst.Name)]


def _body(definition: cst.ClassDef) -> Sequence[cst.BaseStatement]:
    block = definition.body
    return block.body if isinstance(block, cst.IndentedBlock) else ()


def _small(statement: cst.BaseStatement) -> Sequence[cst.BaseSmallStatement]:
    return statement.body if isinstance(statement, cst.SimpleStatementLine) else ()


def _full_name(node: cst.BaseExpression) -> str:
    return get_full_name_for_node(node) or ""
