"""A factory whose parameters are only known once a workflow's configuration is read."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ["injecting_factory"]

_T = TypeVar("_T")


def injecting_factory(
    build: Callable[[Mapping[str, object]], _T], parameters: Mapping[str, object], returns: type
) -> Callable[..., _T]:
    """Return a factory taking ``parameters`` by keyword and handing them to ``build``.

    What a workflow's services take depends on its configuration — the
    qualifier of its marking store, whether a dispatcher is there to hand it —
    so the factory's signature is written at registration rather than in its
    ``def``: the container reads the parameters, each annotated, and the
    return type it registers the factory under. It calls the factory by
    keyword, which is how ``build`` gets them, keyed by name.

    Args:
        build: Builds the service from the arguments the container resolved.
        parameters: The annotation of each parameter, by name.
        returns: The type the factory is registered under.
    """

    def factory(**arguments: object) -> _T:
        return build(arguments)

    signature = inspect.Signature(
        [
            inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
            for name, annotation in parameters.items()
        ],
        return_annotation=returns,
    )
    # Written on the function, as ``inspect.signature`` and the annotation readers look for them.
    setattr(factory, "__signature__", signature)  # noqa: B010 -- a function declares no such attribute
    factory.__annotations__ = {**parameters, "return": returns}
    return factory
