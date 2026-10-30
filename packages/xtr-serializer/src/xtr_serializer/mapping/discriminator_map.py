"""The decorator starting a class hierarchy whose values are written with their class's name."""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, RootModel
from pydantic.dataclasses import is_pydantic_dataclass, rebuild_dataclass

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError

from ._class_discriminator_registry import REGISTRY
from ._field_names import field_names_of
from ._polymorphic_schema import polymorphic_schema

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["discriminator_map"]

_ClassT = TypeVar("_ClassT", bound=type)

# What pydantic asks a class for its schema by.
_HOOK = "__get_pydantic_core_schema__"


def discriminator_map(type_property: str = "$type") -> Callable[[_ClassT], _ClassT]:
    """Make the decorated class the base of a hierarchy written with each value's class name.

    A field declaring the base, or any class under it, holds a value of any subclass: pydantic
    alone writes such a value by the declared class's fields and reads it back as the declared
    class, its own fields lost. Under a hierarchy, the value is written with the name its class
    registered with :func:`~xtr_serializer.discriminator_name` under ``type_property``, then its
    fields, and read back as the class that name stands for — among the subclasses of the class
    declared, so data cannot name a class of another hierarchy, or one the field does not take::

        @discriminator_map()
        @dataclass(frozen=True)
        class Event:
            name: str


        @discriminator_name("delivery")
        @dataclass(frozen=True)
        class Delivery(Event):
            recipient: str

    ``Mailbox(latest=Delivery("sent", "ana@example.com"))`` is written
    ``{"latest": {"$type": "delivery", "name": "sent", "recipient": "ana@example.com"}}``.

    The base is a dataclass, a model or a pydantic dataclass, which pydantic has a schema for. The
    default key is no name a field can have; another must be no field's name or alias. Apply this
    decorator after ``@dataclass``, and before ``@discriminator_name`` when the base has a name
    too. Every class of the hierarchy is named before a type holding one is used — or defined,
    for a model, which builds its schema then (see :func:`~xtr_serializer.discriminator_name`).
    A model or a pydantic dataclass still builds and validates as itself: given the key, it
    reads it and keeps nothing of it.

    Args:
        type_property: The key a value's class name is written under.

    Raises:
        MappingError: If ``type_property`` is empty or a field's name, the class is no dataclass
            or model, a root model or a generic class, is in a hierarchy already, or hands
            pydantic its schema itself.
    """

    def declare(base: _ClassT) -> _ClassT:
        name = qualified_name_of(base)
        if not type_property:
            raise MappingError(f"the type_property of {name!r} must be some text")
        if not _has_fields(base):
            raise MappingError(
                f"{name!r} is no dataclass or model, which pydantic has a schema for"
            )
        if issubclass(base, RootModel):
            raise MappingError(f"{name!r} is a root model, which has no object to name")
        if getattr(base, "__parameters__", ()):
            raise MappingError(f"{name!r} is generic, which pydantic reads by its fields alone")
        # A class in a hierarchy already has its hook and fields checked; it is refused as such.
        if not REGISTRY.in_hierarchy(base):
            if type_property in field_names_of(base):
                raise MappingError(
                    f"{name!r} has a field named or aliased {type_property!r}, which its "
                    "classes' names would be written under"
                )
            if _HOOK in vars(base):
                raise MappingError(f"{name!r} defines {_HOOK} itself, which a hierarchy takes over")
        REGISTRY.add_hierarchy(base, type_property)
        setattr(base, _HOOK, classmethod(polymorphic_schema))
        _rebuild(base)
        return base

    return declare


def _rebuild(base: type[object]) -> None:
    """Build again a base pydantic built before it was declared, so its own schema reads the key.

    One still waiting to be built — deferred, or naming what is not defined yet — is built later
    with the key.
    """
    if issubclass(base, BaseModel):
        if base.__pydantic_complete__:
            _ = base.model_rebuild(force=True, raise_errors=False)
    elif is_pydantic_dataclass(base) and base.__pydantic_complete__:
        _ = rebuild_dataclass(base, force=True, raise_errors=False)


def _has_fields(base: type[object]) -> bool:
    """Whether ``base`` is a dataclass or a model, the classes pydantic reads field by field."""
    return is_dataclass(base) or issubclass(base, BaseModel)
