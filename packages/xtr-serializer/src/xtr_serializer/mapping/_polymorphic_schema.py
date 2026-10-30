"""Where a class of a hierarchy is declared, the union of the named classes it takes."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final, NamedTuple, cast

from pydantic_core import core_schema

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError, NotNormalizableValueError

from ._class_builds import is_unbuilt
from ._class_choice import class_choice
from ._class_discriminator_registry import REGISTRY
from ._declaration_sites import is_declaring
from ._deferred_refusals import refused_or_deferred

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema

    from ._class_discriminator_registry import Members

__all__ = ["polymorphic_schema"]

# What the schema of a class alone is kept under, and the schema a union reads it by: the
# reference pydantic gives the class, then these. The reference itself is the union's.
_OWN: Final = "#xtr_serializer.class_discriminator.own"
_CHOICE: Final = "#xtr_serializer.class_discriminator.choice"

# The error a union reports for data naming no class it takes, under its key.
_ERROR_TYPE: Final = "class_discriminator"
_ERROR_MESSAGE: Final = (
    "the data must be an object whose {!r} names a class the declared type takes"
)


class _Member(NamedTuple):
    """A named class a union takes: the class, the tag the union knows it by, and its name."""

    kind: type
    tag: int
    name: str


def polymorphic_schema(_owner: type, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
    """Build the schema of ``source``, a class of a hierarchy, where it is declared.

    Installed on the base of a hierarchy as the class method pydantic asks every class under it
    for its schema by; ``_owner`` is the class it is asked on, which ``source`` is.

    Wherever a class of a hierarchy is declared — a field, a list's items, the type asked for —
    pydantic asks it for its schema, and gets a tagged union of the named classes it takes, itself
    and its subclasses: each value is written with its class's name under the hierarchy's key,
    then its fields, and read back as the class named, by that class's own schema, from the data
    without its name. pydantic builds a class's schema once in a schema and points every other
    place declaring the class to it by the class's reference: so the union takes that reference,
    and the class's own schema is kept under another, which each union naming the class reads.

    A model, or a dataclass pydantic built, is asked for its schema as it builds itself too, and
    keeps its own schema then — pydantic alone validates it — with the places inside it declaring
    its own class pointing to the union. pydantic tells that build apart from the others by
    nothing the class shows. A type's schema the normalizer builds is never one (see
    :func:`~xtr_serializer.mapping._declaration_sites.declaring`); elsewhere it is taken to be one
    where the class is asked at no field while it is not built yet, so that a type plain pydantic
    builds holding such a class at no field — as the type itself, or the items of one — reads it
    as itself alone.

    A tag the union reads is the place of the class among those it takes, rather than the name
    the data gives: pydantic puts the tag in the location of an error inside the class, where a
    number marks it as no key of the data's.

    Raises:
        MappingError: If no class the declared one takes has a name, or a field of a class has
            the key's name.
    """
    declared = cast("type[object]", source)
    own_build = not is_declaring() and handler.field_name is None and is_unbuilt(declared)
    members = cast("Members", REGISTRY.claim(declared, even_unnamed=not own_build))
    if not members.names and not own_build:
        raise MappingError(
            f"no class {qualified_name_of(declared)!r} takes has a name: name its classes with "
            "@discriminator_name before a type holding it is used"
        )
    # Asked for the class itself, the handler gives the class's schema under its reference — or,
    # for one built already, its own schema, kept where the class's own build put it.
    schema = handler(source)
    ref = cast("str", schema.get("ref")).removesuffix(_OWN)
    own = cast("CoreSchema", cast("object", {**schema, "ref": ref + _OWN}))
    choice = class_choice(own, declared, members.type_property, ref + _CHOICE)
    union = _union(declared, ref, members, handler)
    if own_build:
        top = core_schema.definition_reference_schema(ref + _OWN)
        return core_schema.definitions_schema(top, [union, own, choice])
    return core_schema.definitions_schema(union, [own, choice])


def _union(declared: type, ref: str, members: Members, handler: GetCoreSchemaHandler) -> CoreSchema:
    """Build the tagged union of the named classes ``declared`` takes, under its reference.

    A union of no class, the schema a class built before its classes are named reads its own
    class inside by, refuses every value.
    """
    choices: dict[int, CoreSchema] = {}
    by_class: dict[int, _Member] = {}
    by_name: dict[str, int] = {}
    for tag, (name, member) in enumerate(members.names):
        member_ref = ref if member is declared else _ref_of(handler.generate_schema(member))
        choices[tag] = core_schema.definition_reference_schema(member_ref + _CHOICE)
        # By identity: looking a class up by its hash would run its metaclass's code.
        by_class[id(member)] = _Member(member, tag, name)
        by_name[name] = tag
    key = members.type_property
    return core_schema.tagged_union_schema(
        cast("dict[object, CoreSchema]", choices),
        _tag_reader(key, by_name, by_class),
        custom_error_type=_ERROR_TYPE,
        custom_error_message=_ERROR_MESSAGE.format(key),
        ref=ref,
        serialization=core_schema.wrap_serializer_function_ser_schema(
            _writer(key, declared, by_class)
        )
        if choices
        else core_schema.plain_serializer_function_ser_schema(partial(_refuse_every, declared)),
    )


def _ref_of(schema: CoreSchema) -> str:
    """Give the reference of the class a schema points to: its union, or its own schema."""
    return cast("core_schema.DefinitionReferenceSchema", schema)["schema_ref"].removesuffix(_OWN)


def _member_of(kind: type, by_class: Mapping[int, _Member]) -> _Member | None:
    """Find the member that is ``kind`` itself, by identity."""
    member = by_class.get(id(kind))
    return member if member is not None and member.kind is kind else None


def _tag_reader(
    key: str, by_name: Mapping[str, int], by_class: Mapping[int, _Member]
) -> Callable[[object], int | None]:
    """Make what finds the class to read: named by the data's key, or a given value's class."""

    def class_tag(value: object) -> int | None:
        if issubclass(type(value), dict):
            # Read past any override of the data's own, among the keys that are text exactly,
            # compared as text: no code of the data's runs, as a lookup comparing a key hashed
            # alike would run. A name is text, anything else none.
            items = dict[object, object].items(cast("dict[object, object]", value))
            name = next((item for at, item in items if type(at) is str and at == key), None)
            return by_name.get(name) if type(name) is str else None
        member = _member_of(type(value), by_class)
        return None if member is None else member.tag

    return class_tag


def _writer(
    key: str, declared: type, by_class: Mapping[int, _Member]
) -> Callable[[object, Callable[[object], object]], object]:
    """Make what writes a value's fields after its class's name, refusing a class with none."""

    def write_with_class_name(value: object, write: Callable[[object], object]) -> object:
        kind = type(value)
        member = _member_of(kind, by_class)
        if member is None:
            refusal = _refusal(kind, declared)
            # Under the declared class with no name, the value is written by no other member of
            # a union holding it either: kept as a refusal met inside the value, it is the one
            # reported, rather than the union's own words for a value none of its members wrote.
            if refusal.error_type == "unnamed_class":
                return refused_or_deferred(refusal)
            raise refusal
        fields = write(value)
        if type(fields) is not dict:
            raise NotNormalizableValueError(
                "its class writes no object, which its name would be written in",
                current_type=qualified_name_of(kind),
                error_type="class_discriminator_object",
            )
        if key in cast("dict[str, object]", fields):
            raise NotNormalizableValueError(
                f"an extra field is written under {key!r}, which its class's name is",
                current_type=qualified_name_of(kind),
                error_type="class_discriminator_taken",
            )
        return {key: member.name, **cast("dict[str, object]", fields)}

    return write_with_class_name


def _refuse_every(declared: type, value: object) -> object:
    """Refuse to write ``value`` where ``declared`` is, which took no named class when built."""
    raise NotNormalizableValueError(
        f"no class {qualified_name_of(declared)!r} takes had a name when the schema holding it "
        "was built: a model holding its own hierarchy is defined with defer_build",
        expected_types=(qualified_name_of(declared),),
        current_type=qualified_name_of(type(value)),
        error_type="class_discriminator_unnamed",
    )


def _refusal(kind: type, declared: type) -> NotNormalizableValueError:
    """Say why a value of ``kind`` cannot be written where ``declared`` is."""
    expected = (qualified_name_of(declared),)
    # The interpreter's own check, which runs no code of a metaclass of either.
    if type.__subclasscheck__(declared, kind):
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
