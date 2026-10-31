"""``debug:serializer``: how a class is read and written, and the classes of its hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.mapping.class_discriminator_mapping import ClassDiscriminatorMapping
from xtr_serializer.normalizer._adapter_cache import build_adapter

from ._class_import import import_class
from ._schema_fields import FieldRow, field_rows

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic.json_schema import JsonSchemaMode

__all__ = ["DebugSerializerCommand"]

_MODES: Final[tuple[JsonSchemaMode, ...]] = ("validation", "serialization")
_FIELD_HEADERS: Final = ("Field", "Serialized name", "Type", "Required", "Default")


@as_command("debug:serializer")
@final
class DebugSerializerCommand:
    """Shows the fields of a class as it is read and written, and the classes of its hierarchy."""

    __slots__ = ()

    def __call__(self, io: ConsoleStyle, class_path: str) -> int:
        """Show each field of the class, as it is read and as it is written, then its classes.

        The fields are those of pydantic's JSON schema of the class, built as the pydantic
        normalizer builds it: ``validation`` is how data is read into the class, and
        ``serialization`` how a value of it is written. A class of a hierarchy shows the key its
        class name is written under, and the class each name stands for.

        Args:
            io: Where the command writes.
            class_path: The class, as ``module:Class`` or ``module.Class``.
        """
        found = import_class(class_path)
        if isinstance(found, str):
            return _refused(io, found)
        adapter = build_adapter(found)
        if isinstance(adapter, str):
            return _refused(io, adapter)
        name = _name_of(found)
        # Built after the schema, which keeps names given later out of the hierarchy.
        mapping = ClassDiscriminatorMapping.for_class(found)
        classes = () if mapping is None else tuple(mapping.types_mapping.values())
        member = next((place for place, kind in enumerate(classes) if kind is found), None)
        if mapping is not None and member is None:
            io.title(escape(name))
            io.note(
                "It has no name in its hierarchy, so it is never written itself: a value of it "
                "is one of the classes below."
            )
        else:
            described: dict[JsonSchemaMode, list[FieldRow]] = {}
            for mode in _MODES:
                rows = field_rows(adapter.writer, mode, member)
                if isinstance(rows, str):
                    return _refused(io, f"{name!r} cannot be shown: {rows}")
                described[mode] = rows
            io.title(escape(name))
            _write_fields(io, described)
        if mapping is not None:
            _write_classes(io, mapping)
        return ExitCode.SUCCESS


def _name_of(kind: type) -> str:
    return f"{kind.__module__}.{qualified_name_of(kind)}"


def _refused(io: ConsoleStyle, why: str) -> int:
    io.error(escape(why))
    return ExitCode.FAILURE


def _write_fields(io: ConsoleStyle, described: Mapping[JsonSchemaMode, list[FieldRow]]) -> None:
    """Write a table of the fields per mode."""
    for mode, rows in described.items():
        io.section(mode)
        if rows:
            io.table(_FIELD_HEADERS, [[escape(cell) for cell in row] for row in rows])
        else:
            io.text("No field.")


def _write_classes(io: ConsoleStyle, mapping: ClassDiscriminatorMapping) -> None:
    """Write the key a class name is written under, and the class each name stands for."""
    io.section("discriminator map")
    io.text(f"Type property: {escape(mapping.type_property)}")
    io.table(
        ("Name", "Class"),
        [(escape(one), escape(_name_of(kind))) for one, kind in mapping.types_mapping.items()],
    )
