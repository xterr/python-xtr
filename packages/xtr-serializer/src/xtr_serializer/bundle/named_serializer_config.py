"""The configuration of one serializer registered under a name of its own."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from xtr_serializer.exception import InvalidArgumentError

from ._context_check import check_context

__all__ = ["NamedSerializerConfig"]


@dataclass(frozen=True, slots=True)
class NamedSerializerConfig:
    """How a named serializer differs from the default one.

    A named serializer is for a part of the application that writes differently — an API whose
    clients expect other options, a store that keeps only some types. It gets the normalizers
    and encoders tagged for its name, or for every serializer, and the built-in ones unless it
    leaves them out.

    Attributes:
        default_context: Options every call to it starts from, over the bundle's own
            ``default_context`` key by key; a call's context still wins over both.
        include_built_in_normalizers: Whether the bundle's own normalizers join it. Left out,
            the serializer has only the normalizers tagged for it, and must be given one.
        include_built_in_encoders: Whether the bundle's own encoders join it. Left out, the
            serializer has only the encoders tagged for it, and must be given one.
    """

    default_context: Mapping[str, object] = field(default_factory=dict[str, object])
    include_built_in_normalizers: bool = True
    include_built_in_encoders: bool = True

    def __post_init__(self) -> None:
        """Refuse a default context keyed by something else than strings, and a switch not a bool.

        A configuration is written by hand, and its annotations are not enforced: a ``"no"``
        or a ``0`` read as a switch would say the opposite of what was meant, or nothing at all.

        Raises:
            InvalidArgumentError: When the configuration cannot be read.
        """
        check_context(self.default_context, "a named serializer's default context")
        switches: dict[str, object] = {
            "include_built_in_normalizers": self.include_built_in_normalizers,
            "include_built_in_encoders": self.include_built_in_encoders,
        }
        for name, value in switches.items():
            if not isinstance(value, bool):
                raise InvalidArgumentError(
                    f"a named serializer's {name} is True or False, "
                    f"not a value of type {type(value).__name__}"
                )
