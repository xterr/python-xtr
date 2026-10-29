"""RelationWriter: one relation, written as the attributes, keys and table each side needs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from xtr_maker.class_name import ClassName
from xtr_maker.exception import InvalidArgumentError
from xtr_maker.import_collector import ImportCollector
from xtr_maker.name_converter import NameConverter

from .id_type import IdType
from .mapped_attribute import MappedAttribute
from .relation_kind import RelationKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_maker.generator import Generator

    from .entity_relation import EntityRelation
    from .entity_source_editor import EntitySourceEditor

__all__ = ["RelationWriter"]

_ASSOCIATION_TEMPLATE: Final = "entity/association_table.py.jinja"


@dataclass(frozen=True, slots=True)
class _Shape:
    """One side's ``relationship``: its name, what it reaches, and the side it mirrors."""

    name: str
    back_populates: str | None
    collection: bool = False
    nullable: bool = False
    secondary: str | None = None


@final
class RelationWriter:
    """Adds a relation to the entity being made, and its inverse to the other entity.

    The side holding the key gets ``<name>_id``, a ``ForeignKey`` to the
    other table's ``id`` typed after the other entity's key, beside the
    ``relationship``. A ``many_to_many`` relation gets an association table,
    in a module of its own next to the entity, which both sides name as
    ``secondary``. The other entity is imported for annotations only: the
    relationship finds it by name once every entity is mapped.

    Every name is checked before anything is added, so a relation that is
    refused leaves both entities as they were.
    """

    __slots__ = ("_generator",)

    def __init__(self, generator: Generator) -> None:
        """Queue association tables with ``generator``.

        Args:
            generator: What writes a ``many_to_many`` relation's table.
        """
        self._generator = generator

    def write(
        self, relation: EntityRelation, owner: EntitySourceEditor, target: EntitySourceEditor
    ) -> None:
        """Add ``relation`` to ``owner``, and its inverse, if any, to ``target``.

        Raises:
            InvalidArgumentError: When a name is taken, the key type of an
                entity cannot be told, or a ``many_to_many`` relation targets
                its own entity.
            TargetExistsError: When the association table's module exists.
        """
        _check(relation, owner, target)
        name, inverse, nullable = relation.name, relation.inverse, relation.nullable
        match relation.kind:
            case RelationKind.MANY_TO_ONE | RelationKind.ONE_TO_ONE:
                unique = relation.kind is RelationKind.ONE_TO_ONE
                _add(owner, lambda imports: _key(imports, name, target, (nullable, unique)))
                _add(owner, _relationship(owner, target, _Shape(name, inverse, nullable=nullable)))
                if inverse is not None:
                    shape = _Shape(inverse, name, collection=not unique, nullable=unique)
                    _add(target, _relationship(target, owner, shape))
            case RelationKind.ONE_TO_MANY:
                back = inverse or ""
                _add(owner, _relationship(owner, target, _Shape(name, back, collection=True)))
                _add(target, lambda imports: _key(imports, back, owner, (nullable, False)))
                _add(target, _relationship(target, owner, _Shape(back, name, nullable=nullable)))
            case RelationKind.MANY_TO_MANY:
                table = self._association(owner, target)
                shape = _Shape(name, inverse, collection=True, secondary=table)
                _add(owner, _relationship(owner, target, shape))
                if inverse is not None:
                    shape = _Shape(inverse, name, collection=True, secondary=table)
                    _add(target, _relationship(target, owner, shape))

    def _association(self, owner: EntitySourceEditor, target: EntitySourceEditor) -> str:
        """Queue the association table's module, and return ``module:variable``."""
        entity = owner.entity
        association = ClassName(
            entity.root_package, entity.package, f"{entity.short_name}{target.entity.short_name}"
        )
        variable = f"{association.snake_name}_table"
        imports = ImportCollector(entity.root_package)
        registry = imports.add("advanced_alchemy.base", "orm_registry")
        context = {
            "variable": variable,
            "table": NameConverter.as_table_name(association.short_name),
            "metadata": f"{registry}.metadata",
            "column": imports.add("sqlalchemy", "Column"),
            "foreign_key": imports.add("sqlalchemy", "ForeignKey"),
            "table_class": imports.add("sqlalchemy", "Table"),
            "columns": [
                (
                    _python_type(imports, side),
                    _literal(f"{side.entity.snake_name}_id"),
                    _literal(f"{_table(side)}.id"),
                )
                for side in (owner, target)
            ],
            "owner_table": _table(owner),
            "target_table": _table(target),
        }
        context["imports"] = imports.render()
        _ = self._generator.generate_class(association, _ASSOCIATION_TEMPLATE, context)
        return f"{association.module}:{variable}"


def _check(relation: EntityRelation, owner: EntitySourceEditor, target: EntitySourceEditor) -> None:
    """Refuse the relation before anything is added when any name it adds is taken."""
    if relation.kind is RelationKind.MANY_TO_MANY and owner is target:
        raise InvalidArgumentError(
            "A many_to_many relation from an entity to itself is not supported."
        )
    added = [(owner, relation.name)]
    if relation.kind.holds_key:
        added.append((owner, relation.key_name))
    if relation.inverse is not None:
        added.append((target, relation.inverse))
        if relation.kind is RelationKind.ONE_TO_MANY:
            added.append((target, f"{relation.inverse}_id"))
    seen: set[tuple[int, str]] = set()
    for editor, name in added:
        if editor.has_attribute(name) or (id(editor), name) in seen:
            raise InvalidArgumentError(
                f"{editor.entity.short_name} already has a property {name!r}."
            )
        seen.add((id(editor), name))
    for editor in (owner, target):
        _ = _id_type(editor)


def _add(
    editor: EntitySourceEditor, attribute: Callable[[ImportCollector], MappedAttribute]
) -> None:
    imports = editor.imports()
    editor.add_attribute(attribute(imports), imports)


def _key(
    imports: ImportCollector, name: str, referenced: EntitySourceEditor, flags: tuple[bool, bool]
) -> MappedAttribute:
    """Return ``<name>_id``, the key to ``referenced``; ``flags`` are (nullable, unique)."""
    nullable, unique = flags
    python = _python_type(imports, referenced)
    foreign_key = imports.add("sqlalchemy", "ForeignKey")
    arguments = [f"{foreign_key}({_literal(f'{_table(referenced)}.id')})"]
    if unique:
        arguments.append("unique=True")
    if nullable:
        arguments.append("nullable=True")
    return MappedAttribute(
        f"{name}_id",
        f"{python} | None" if nullable else python,
        imports.add("sqlalchemy.orm", "mapped_column"),
        tuple(arguments),
        imports.add("sqlalchemy.orm", "Mapped"),
    )


def _relationship(
    holder: EntitySourceEditor, other: EntitySourceEditor, shape: _Shape
) -> Callable[[ImportCollector], MappedAttribute]:
    """Return what builds ``holder``'s ``relationship`` to ``other``, shaped by ``shape``."""

    def build(imports: ImportCollector) -> MappedAttribute:
        entity = other.entity
        reached = (
            entity.short_name
            if other is holder
            else imports.add(entity.module, entity.short_name, type_checking=True)
        )
        annotation = f"list[{reached}]" if shape.collection else reached
        if shape.nullable:
            annotation = f"{annotation} | None"
        arguments: list[str] = []
        if shape.secondary is not None:
            module, _, variable = shape.secondary.partition(":")
            arguments.append(f"secondary={imports.add(module, variable)}")
        if shape.back_populates is not None:
            arguments.append(f"back_populates={_literal(shape.back_populates)}")
        return MappedAttribute(
            shape.name,
            annotation,
            imports.add("sqlalchemy.orm", "relationship"),
            tuple(arguments),
            imports.add("sqlalchemy.orm", "Mapped"),
        )

    return build


def _id_type(editor: EntitySourceEditor) -> IdType:
    found = IdType.of_bases(editor.bases)
    if found is None:
        raise InvalidArgumentError(
            f"The key type of {editor.entity.short_name} cannot be told: it derives from"
            " none of the UUID or BigInt bases."
        )
    return found


def _python_type(imports: ImportCollector, editor: EntitySourceEditor) -> str:
    """Return the type a key to ``editor``'s entity holds, imported into ``imports``."""
    module, name = _id_type(editor).python_type
    return name if module == "builtins" else imports.add(module, name)


def _table(editor: EntitySourceEditor) -> str:
    return editor.table_name or NameConverter.as_table_name(editor.entity.short_name)


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)
