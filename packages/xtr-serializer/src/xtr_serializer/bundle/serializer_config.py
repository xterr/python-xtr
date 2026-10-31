"""Configuration for :class:`~xtr_serializer.bundle.SerializerBundle`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from xtr_serializer.exception import InvalidArgumentError

from ._context_check import check_context
from .named_serializer_config import NamedSerializerConfig

__all__ = ["ALL_SERIALIZERS", "DEFAULT_SERIALIZER", "SerializerConfig"]

DEFAULT_SERIALIZER: Final = "default"
"""The name a tag gives the default serializer by, which no named serializer may take."""

ALL_SERIALIZERS: Final = "*"
"""The name a tag gives every serializer by, which no named serializer may take."""


@dataclass(frozen=True, slots=True)
class SerializerConfig:
    """How the bundle builds the container's serializers.

    Buildable with no arguments: an application listing the bundle without configuring it gets
    one serializer writing JSON, with every normalizer and encoder it registers.

    ```python
    SerializerConfig(
        default_context={STRICT: True},
        named_serializers={"api": NamedSerializerConfig(default_context={SKIP_NULL_VALUES: True})},
    )
    ```

    Attributes:
        default_context: Options every call to every serializer starts from; a call's context
            wins over them key by key.
        named_serializers: Serializers besides the default one, each registered under its name
            as the qualifier. ``"default"`` and ``"*"`` are the names tags use for the default
            serializer and for all of them, so neither names one here.
    """

    default_context: Mapping[str, object] = field(default_factory=dict[str, object])
    named_serializers: Mapping[str, NamedSerializerConfig] = field(
        default_factory=dict[str, NamedSerializerConfig]
    )

    def __post_init__(self) -> None:
        """Refuse a context keyed by something else than strings, and named serializers unread.

        The named serializers are a mapping of non-empty names, none reserved, to
        :class:`NamedSerializerConfig`.

        Raises:
            InvalidArgumentError: When the configuration cannot be read.
        """
        check_context(self.default_context, "the default context")
        if not isinstance(self.named_serializers, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                "named_serializers is a mapping of names to NamedSerializerConfig, not a value of "
                f"type {type(self.named_serializers).__name__}"
            )
        for name, named in self.named_serializers.items():
            if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
                raise InvalidArgumentError(
                    f"a named serializer needs a non-empty name, got {name!r}"
                )
            if name in {DEFAULT_SERIALIZER, ALL_SERIALIZERS}:
                raise InvalidArgumentError(
                    f"{name!r} is reserved: tags name the default serializer "
                    f"{DEFAULT_SERIALIZER!r} and every serializer {ALL_SERIALIZERS!r}, so a named "
                    f"serializer takes another"
                )
            if not isinstance(named, NamedSerializerConfig):  # pyright: ignore[reportUnnecessaryIsInstance] -- as above
                raise InvalidArgumentError(
                    f"the serializer {name!r} is configured with a NamedSerializerConfig, "
                    f"not a value of type {type(named).__name__}"
                )
