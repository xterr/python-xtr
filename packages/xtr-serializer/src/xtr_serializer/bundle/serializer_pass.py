"""Hands every serializer the normalizers and encoders tagged for it, in the order it tries them."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from typing import Final, cast, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface, ContainerBuilder, ServiceKey

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import LogicError
from xtr_serializer.serializer import Serializer

from ._serializer_factory import serializer_factory
from .named_serializer_config import NamedSerializerConfig
from .serializer_config import ALL_SERIALIZERS, DEFAULT_SERIALIZER, SerializerConfig

__all__ = ["ENCODER_TAG", "NORMALIZER_TAG", "SerializerPass"]

NORMALIZER_TAG: Final = "serializer.normalizer"
"""The tag a normalizer, a denormalizer or both carry to join a serializer.

It takes three attributes, each optional:

- ``priority`` — an ``int``, higher tried first; without it, the definition's own priority, or 0;
- ``serializer`` — the name of the serializer it joins, or a sequence of names: ``"default"``
  (the default when absent), a configured name, or ``"*"`` for every serializer;
- ``built_in`` — ``True`` for one a named serializer can leave out with
  ``include_built_in_normalizers=False``.

A class subclassing ``NormalizerInterface`` or ``DenormalizerInterface`` carries it without being
told, with no attribute; a bundle tagging it explicitly gives the attributes it needs::

    services.set(MoneyNormalizer).add_tag(NORMALIZER_TAG, priority=10, serializer="*")
"""

ENCODER_TAG: Final = "serializer.encoder"
"""The tag an encoder, a decoder or both carry to join a serializer.

Its attributes, and the classes tagged without being told, are those of :data:`NORMALIZER_TAG`,
with ``include_built_in_encoders`` deciding for a built-in one.
"""


@dataclass(frozen=True, slots=True)
class _Tagged:
    """One tag on a service, read: where it goes, and how early it is tried."""

    key: ServiceKey
    priority: int
    serializers: frozenset[str]
    built_in: bool

    def joins(self, name: str, *, built_ins: bool) -> bool:
        """Tell whether this joins the serializer ``name``, keeping built-ins or not."""
        named = name in self.serializers or ALL_SERIALIZERS in self.serializers
        return named and (built_ins or not self.built_in)


@final
class SerializerPass(CompilerPassInterface):
    """Gives every serializer the services tagged for it, highest priority first.

    A serializer is the default one, registered unqualified, and one per configured name,
    registered under that name. The pass reads the services tagged :data:`NORMALIZER_TAG` and
    :data:`ENCODER_TAG`, picks those each serializer is to hold — by the tag's ``serializer``
    and, for a built-in one, whether a named serializer keeps built-ins — orders them by
    priority, then by the order they were registered in, and writes the serializer's factory to
    take exactly those. A mistake in a tag, or a serializer left with nothing to convert or
    nothing to write with, fails the build rather than the first call.

    A named serializer gets its own instance of every service it shares with another — a service
    is handed the serializer holding it, and one instance can only be handed one. A service
    provided as an object, rather than built by the container, cannot be copied and is shared.

    :class:`~xtr_serializer.bundle.SerializerBundle` registers it behind every bundle's
    ``process`` hook, so a service another bundle tags there joins too.
    """

    __slots__ = ()

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Write the factory of every serializer.

        Raises:
            LogicError: When a tag cannot be read or names a serializer that does not exist, or
                a serializer is left without a normalizer or an encoder.
        """
        config = builder.get_extension_config(SerializerConfig)
        serializers: dict[str, NamedSerializerConfig | None] = {DEFAULT_SERIALIZER: None}
        serializers |= config.named_serializers
        own = {(Serializer, _qualifier(name)) for name in serializers}
        normalizers = _tagged(builder, NORMALIZER_TAG, own, serializers)
        encoders = _tagged(builder, ENCODER_TAG, own, serializers)
        for name, named in serializers.items():
            built_in_normalizers = named is None or named.include_built_in_normalizers
            built_in_encoders = named is None or named.include_built_in_encoders
            normalizer_keys = _held(
                name, normalizers, NORMALIZER_TAG, built_ins=built_in_normalizers
            )
            encoder_keys = _held(name, encoders, ENCODER_TAG, built_ins=built_in_encoders)
            qualifier = _qualifier(name)
            definition = builder.get_definition(Serializer, qualifier)
            definition.provider = serializer_factory(
                qualifier,
                [_own_instance(builder, key, qualifier) for key in normalizer_keys],
                [_own_instance(builder, key, qualifier) for key in encoder_keys],
            )
            definition.kind = "factory"


def _qualifier(name: str) -> str | None:
    """Return the qualifier the serializer ``name`` is registered under."""
    return None if name == DEFAULT_SERIALIZER else name


def _tagged(
    builder: ContainerBuilder,
    tag: str,
    own: AbstractSet[ServiceKey],
    serializers: Mapping[str, object],
) -> list[_Tagged]:
    """Return every tag ``tag`` on a service other than a serializer, in registration order."""
    found: list[_Tagged] = []
    for key, attribute_list in builder.find_tagged_service_ids(tag).items():
        # A serializer is itself a normalizer and an encoder, and holds no serializer.
        if key not in own:
            fallback = builder.get_definition(*key).priority or 0
            found.extend(
                _read(key, attributes, fallback, serializers) for attributes in attribute_list
            )
    return found


def _read(
    key: ServiceKey,
    attributes: Mapping[str, object],
    fallback: int,
    serializers: Mapping[str, object],
) -> _Tagged:
    """Read one tag's attributes.

    Raises:
        LogicError: When an attribute is of the wrong kind or names a serializer that does not
            exist.
    """
    service = qualified_name_of(key[0]) + ("" if key[1] is None else f"[{key[1]!r}]")
    priority = attributes.get("priority", fallback)
    named = attributes.get("serializer", DEFAULT_SERIALIZER)
    built_in = attributes.get("built_in", False)
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise LogicError(f"{service} is tagged with a priority that is not an integer")
    if not isinstance(built_in, bool):
        raise LogicError(f"{service} is tagged with a built_in that is not a boolean")
    candidates = [named] if isinstance(named, str) else named
    if not isinstance(candidates, Sequence):
        raise LogicError(f"{service} is tagged with a serializer that is not a name or names")
    given = cast("Sequence[object]", candidates)
    names = [one for one in given if isinstance(one, str)]
    if len(names) != len(given):
        raise LogicError(f"{service} is tagged with a serializer that is not a name or names")
    for one in names:
        if one != ALL_SERIALIZERS and one not in serializers:
            raise LogicError(
                f"{service} is tagged for the serializer {one!r}, which does not exist: "
                f"add it to SerializerConfig.named_serializers"
            )
    return _Tagged(key, priority, frozenset(names), built_in)


def _held(name: str, tagged: Sequence[_Tagged], tag: str, *, built_ins: bool) -> list[ServiceKey]:
    """Return the services tagged ``tag`` the serializer ``name`` holds, highest priority first.

    Each once, at its first tag that joins; ``sorted`` keeps registration order among equals.

    Raises:
        LogicError: When it holds none.
    """
    joining = (one for one in tagged if one.joins(name, built_ins=built_ins))
    held = list(dict.fromkeys(one.key for one in sorted(joining, key=lambda one: -one.priority)))
    if not held:
        kind = tag.rpartition(".")[2]
        raise LogicError(
            f"the serializer {name!r} has no {kind}: tag one {tag!r} for it, "
            f"or keep the built-in ones"
        )
    return held


def _own_instance(builder: ContainerBuilder, key: ServiceKey, qualifier: str | None) -> ServiceKey:
    """Return the key of the instance of ``key`` the serializer ``qualifier`` holds.

    The default serializer holds the service itself; a named one a copy of its definition,
    under a qualifier of its own and carrying no tag, so no serializer collects it again. A
    service both normalizer and encoder is copied twice to the same key, which stays one
    instance.
    """
    definition = builder.get_definition(*key)
    if qualifier is None or definition.kind == "instance":
        return key
    copy: ServiceKey = (
        key[0],
        f"serializer.{qualifier}" + ("" if key[1] is None else f".{key[1]}"),
    )
    _ = builder.set_definition(
        replace(definition, key=copy, tags={}, arguments=dict(definition.arguments), decorates=None)
    )
    return copy
