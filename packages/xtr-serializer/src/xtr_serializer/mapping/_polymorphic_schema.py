"""The schema a class of a hierarchy is read and written by: a union of its named subclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel
from pydantic.dataclasses import is_pydantic_dataclass
from pydantic_core import core_schema

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError, NotNormalizableValueError

from ._class_discriminator_registry import REGISTRY
from ._tag_field import with_tag_field

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema

    from ._class_discriminator_registry import Members

__all__ = ["polymorphic_schema"]

# What the schema of a class alone is kept under: the reference pydantic gives the class, then this.
_CHOICE: Final = "#xtr_serializer.class_discriminator.choice"

# The error a union reports for data naming no class it takes, under its key.
_ERROR_TYPE: Final = "class_discriminator"
_ERROR_MESSAGE: Final = (
    "the data must be an object whose {!r} names a class the declared type takes"
)


def polymorphic_schema(_owner: type, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
    """Build the schema of ``source``, a class of a hierarchy.

    Installed on the base of a hierarchy as the class method pydantic asks every class under it
    for its schema by; ``_owner`` is the class it is asked on, which ``source`` is.

    Wherever a class of a hierarchy is declared — a field, a list's items, the type asked for —
    pydantic asks it for its schema, and gets a tagged union of the named classes it takes, itself
    and its subclasses: each value is written with its class's name under the hierarchy's key,
    then its fields, and read back as the class named. pydantic builds a class's schema once in a
    schema and points every other place declaring the class to it, by the class's reference: so
    the union takes that reference, and the class's own schema is kept under another, for unions
    to choose. A union naming a subclass points to the subclass's own schema the same way,
    building the subclass's union first if it was not built yet — so every class of a hierarchy is
    a union wherever it is declared, inside its own classes too.

    A model, or a dataclass pydantic built, is asked for its schema as it builds itself, too: the
    one it is made and validated with, which stays its own schema, reading the key and dropping
    it. pydantic tells that build from the others by none of what a class shows, only by the class
    being built yet or not — so a class that is not built yet is given its own schema wherever it
    is asked: one deferred, or naming what is not defined yet, is read as itself alone in a type
    built before it. A class built once its classes have names — deferred, for one holding its
    own class — reads its own class inside as the union.

    Raises:
        MappingError: If no class the declared one takes has a name, or one cannot carry it.
    """
    declared = cast("type", source)
    # Asked for the class itself, the handler gives the class's schema under its reference — or,
    # for one that built itself already, the schema its own was chosen from.
    schema = handler(source)
    ref = cast("str", schema.get("ref")).removesuffix(_CHOICE)
    members = cast("Members", REGISTRY.claim(declared))
    own = with_tag_field(schema, members.type_property)
    if not members.names:
        if _unbuilt(declared):
            return own
        raise MappingError(
            f"no class {qualified_name_of(declared)!r} takes has a name: name its classes with "
            "@discriminator_name before a type holding it is used"
        )
    union = _union(declared, ref, members, handler)
    choice = _under(own, ref + _CHOICE)
    if _unbuilt(declared):
        return core_schema.definitions_schema(
            core_schema.definition_reference_schema(ref + _CHOICE), [union, choice]
        )
    return core_schema.definitions_schema(union, [choice])


def _under(schema: CoreSchema, ref: str) -> CoreSchema:
    """Copy ``schema`` under another reference."""
    return cast("CoreSchema", cast("object", {**schema, "ref": ref}))


def _union(declared: type, ref: str, members: Members, handler: GetCoreSchemaHandler) -> CoreSchema:
    """Build the tagged union of the named classes ``declared`` takes, under its reference."""
    choices: dict[object, CoreSchema] = {}
    for name, member in members.names:
        member_ref = ref if member is declared else _ref_of(handler.generate_schema(member))
        choices[name] = core_schema.definition_reference_schema(member_ref + _CHOICE)
    names = {member: name for name, member in members.names}
    key = members.type_property
    return core_schema.tagged_union_schema(
        choices,
        _tag_reader(key, names),
        custom_error_type=_ERROR_TYPE,
        custom_error_message=_ERROR_MESSAGE.format(key),
        ref=ref,
        serialization=core_schema.wrap_serializer_function_ser_schema(
            _writer(key, declared, names)
        ),
    )


def _unbuilt(declared: type[object]) -> bool:
    """Whether ``declared`` is a class pydantic builds, not built yet or being built again."""
    built_by_pydantic = issubclass(declared, BaseModel) or is_pydantic_dataclass(declared)
    return built_by_pydantic and vars(declared).get("__pydantic_complete__") is not True


def _ref_of(schema: CoreSchema) -> str:
    """Give the reference of the class a schema stands for: its union, or its own schema."""
    return cast("core_schema.DefinitionReferenceSchema", schema)["schema_ref"].removesuffix(_CHOICE)


def _tag_reader(key: str, names: Mapping[type, str]) -> Callable[[object], str | None]:
    """Make what finds the name of the class to read: the data's, or a given value's class's."""

    def class_name(value: object) -> str | None:
        if isinstance(value, dict):
            # Read past any override of the data's own; a name is text, anything else none.
            tag = dict[object, object].get(cast("dict[object, object]", value), key)
            return tag if type(tag) is str else None
        return names.get(type(value))

    return class_name


def _writer(
    key: str, declared: type, names: Mapping[type, str]
) -> Callable[[object, Callable[[object], object]], object]:
    """Make what writes a value's fields after its class's name, refusing a class with none."""

    def write_with_class_name(value: object, write: Callable[[object], object]) -> object:
        kind = type(value)
        name = names.get(kind)
        if name is None:
            raise _refusal(kind, declared)
        fields = cast("dict[str, object]", write(value))
        if key in fields:
            raise NotNormalizableValueError(
                f"an extra field is written under {key!r}, which its class's name is",
                current_type=qualified_name_of(kind),
                error_type="class_discriminator_taken",
            )
        return {key: name, **fields}

    return write_with_class_name


def _refusal(kind: type, declared: type) -> NotNormalizableValueError:
    """Say why a value of ``kind`` cannot be written where ``declared`` is."""
    expected = (qualified_name_of(declared),)
    if issubclass(kind, declared):
        return NotNormalizableValueError(
            "its class has no name in its hierarchy to be written under: give it one with "
            "@discriminator_name",
            expected_types=expected,
            current_type=qualified_name_of(kind),
            error_type="unnamed_class",
        )
    return NotNormalizableValueError(
        "the value is not of the declared class or one of its subclasses",
        expected_types=expected,
        current_type=qualified_name_of(kind),
        error_type="unexpected_class",
    )
