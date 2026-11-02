"""Whether pydantic built a class it builds itself, and building it again."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.dataclasses import is_pydantic_dataclass, rebuild_dataclass

__all__ = ["is_unbuilt", "rebuild"]


def is_unbuilt(kind: type[object]) -> bool:
    """Whether ``kind`` is a class pydantic builds, not built yet or being built again.

    Read from the class itself, as a subclass shows the flag of the base it derives from.
    """
    built_by_pydantic = issubclass(kind, BaseModel) or is_pydantic_dataclass(kind)
    return built_by_pydantic and vars(kind).get("__pydantic_complete__") is not True


def rebuild(kind: type[object], *, force: bool) -> None:
    """Build ``kind`` if pydantic builds it, again if ``force``, leaving it unbuilt on errors.

    A class naming what is not defined yet stays unbuilt, for pydantic to build on first use.
    """
    if issubclass(kind, BaseModel):
        _ = kind.model_rebuild(force=force, raise_errors=False)
    elif is_pydantic_dataclass(kind):
        _ = rebuild_dataclass(kind, force=force, raise_errors=False)
