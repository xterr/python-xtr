"""The factory a serializer the container builds is registered with, written per serializer."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Final, cast

from xtr_dependency_injection import ServiceKey, Target

from xtr_serializer.encoder.decoder_interface import DecoderInterface
from xtr_serializer.encoder.encoder_interface import EncoderInterface
from xtr_serializer.normalizer.denormalizer_interface import DenormalizerInterface
from xtr_serializer.normalizer.normalizer_interface import NormalizerInterface
from xtr_serializer.serializer import Serializer

__all__ = ["serializer_factory"]

_NOT_IN_A_NAME: Final = re.compile(r"\W")
"""What a serializer's name may hold that a function's may not, as in ``api.v2``."""


def serializer_factory(
    name: str | None, normalizer_keys: Sequence[ServiceKey], encoder_keys: Sequence[ServiceKey]
) -> Callable[..., Serializer]:
    """Return the factory of the serializer ``name`` — the default one for ``None``.

    Which services a serializer holds is known only once every bundle has registered and the
    pass has read the tags, so the factory's signature is written then, not in a ``def``: one
    keyword parameter per service, in the order the serializer tries them, each annotated with
    the service's type and, when it has one, its qualifier. The container reads that signature
    and resolves each service; the serializer is never handed the container itself. Its
    ``default_context`` is a definition argument, so an ``env()`` placeholder in it is resolved
    when the serializer is built.

    Args:
        name: The serializer's name, which the function is named after in the container's
            report.
        normalizer_keys: The keys of its normalizers, highest priority first.
        encoder_keys: The keys of its encoders, highest priority first.
    """
    normalizer_names = [f"normalizer_{index}" for index in range(len(normalizer_keys))]
    encoder_names = [f"encoder_{index}" for index in range(len(encoder_keys))]

    def serializer(**arguments: object) -> Serializer:
        return Serializer(
            [
                cast("NormalizerInterface | DenormalizerInterface", arguments[one])
                for one in normalizer_names
            ],
            [cast("EncoderInterface | DecoderInterface", arguments[one]) for one in encoder_names],
            cast("Mapping[str, object]", arguments["default_context"]),
        )

    parameters: dict[str, object] = {"default_context": Mapping[str, object]}
    parameters |= {
        one: _annotation(key) for one, key in zip(normalizer_names, normalizer_keys, strict=True)
    }
    parameters |= {
        one: _annotation(key) for one, key in zip(encoder_names, encoder_keys, strict=True)
    }
    # Written on the function, as ``inspect.signature`` and the annotation readers look for them.
    setattr(  # noqa: B010 -- a function declares no such attribute
        serializer,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter(one, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
                for one, annotation in parameters.items()
            ],
            return_annotation=Serializer,
        ),
    )
    serializer.__annotations__ = {**parameters, "return": Serializer}
    if name is not None:
        serializer.__name__ = "serializer_" + _NOT_IN_A_NAME.sub("_", name)
    serializer.__qualname__ = serializer.__name__
    return serializer


def _annotation(key: ServiceKey) -> object:
    """Return what names the service ``key`` to the container: its type, and its qualifier."""
    provided, qualifier = key
    if qualifier is None:
        return provided
    return Annotated[provided, Target(qualifier)]  # ty: ignore[invalid-type-form] -- the type is only known here, at runtime
