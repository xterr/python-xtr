"""The decorator naming a class of a hierarchy, the name its values are written under."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError

from ._class_discriminator_registry import REGISTRY
from ._field_names import field_names_of

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["discriminator_name"]

_ClassT = TypeVar("_ClassT", bound=type)

# What pydantic asks a class for its schema by, which the hierarchy's base answers.
_HOOK = "__get_pydantic_core_schema__"


def discriminator_name(name: str) -> Callable[[_ClassT], _ClassT]:
    """Write the values of the decorated class under ``name``, and read ``name`` back as it.

    The class derives from the base of a hierarchy (see
    :func:`~xtr_serializer.discriminator_map`), the base included. Only a named class is written:
    a value of a subclass without a name is refused rather than written as its base — name the
    subclass too, even one adding no field, for it to come back as itself. A class without a name
    in between, such as an abstract one, is no value of its own, yet a field may declare it, and
    then takes the named classes under it.

    A name is the data's word for the class, kept in what was written: choose one that stays
    when the class moves or is renamed. A schema holding the hierarchy holds the names its classes
    had when it was built: so name every class before a type holding one is used — and before a
    model holding one is defined, as a model builds its schema then. A model holding its own
    hierarchy, such as a thread holding its replies, is a model naming itself after its schema is
    built: define it with ``model_config = ConfigDict(defer_build=True)``. A model or a pydantic
    dataclass not built yet when a type holding it is built — deferred, or naming what is not
    defined yet — is read as itself alone in that type, as pydantic asks it for the schema it
    builds itself with: use it once first, so that it is built. A value of another class then
    sitting there is refused rather than changed.

    Raises:
        MappingError: If ``name`` is empty or taken in the hierarchy, the class is generic, in
            no hierarchy or two, has a name already, has a field named or aliased the
            hierarchy's key, hands pydantic its schema itself, or is named after a schema was
            built for one of its bases.
    """

    def register(kind: _ClassT) -> _ClassT:
        class_name = qualified_name_of(kind)
        if not name:
            raise MappingError(f"the name of {class_name!r} must be some text")
        if getattr(kind, "__parameters__", ()):
            raise MappingError(
                f"{class_name!r} is generic, which pydantic reads by its fields alone"
            )
        key = REGISTRY.type_property_of(kind)
        if key is None:
            raise MappingError(
                f"{class_name!r} is in no hierarchy: it derives from no class decorated with "
                "@discriminator_map"
            )
        if key in field_names_of(kind):
            raise MappingError(
                f"{class_name!r} has a field named or aliased {key!r}, which its name would be "
                "written under"
            )
        # The first class answering pydantic must be the base, with the hierarchy's answer.
        if not REGISTRY.is_root(next(base for base in kind.__mro__ if _HOOK in vars(base))):
            raise MappingError(
                f"{class_name!r} defines {_HOOK} itself, which its hierarchy answers"
            )
        REGISTRY.register(kind, name)
        return kind

    return register
