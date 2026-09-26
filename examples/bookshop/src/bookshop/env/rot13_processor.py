"""A custom prefix: ``env("rot13:NAME")``."""

from __future__ import annotations

import codecs
from collections.abc import Callable, Mapping
from typing import final

from typing_extensions import override
from xtr_dependency_injection import EnvVarProcessorInterface, as_service

__all__ = ["Rot13Processor"]


@final
@as_service
class Rot13Processor(EnvVarProcessorInterface):
    """Decodes a ROT13 value — the prefix ``rot13``.

    Implementing ``EnvVarProcessorInterface`` is all it takes: the kernel bundle's nominal
    autoconfiguration tags it, and the container consults it for every prefix
    :meth:`get_provided_types` names. A prefix nothing provides is refused when the
    container compiles (``EnvPlaceholderError``). Naming a built-in prefix replaces it.
    """

    @override
    def get_env(self, prefix: str, name: str, get_env: Callable[[str], object]) -> object:
        # ``name`` is what follows the prefix: a variable, or a further chain such as
        # "file:SECRET" — ``get_env`` resolves it either way.
        return codecs.decode(str(get_env(name)), "rot13")

    @override
    @classmethod
    def get_provided_types(cls) -> Mapping[str, str]:
        return {"rot13": "string"}
