"""Whether pydantic built a class it builds itself, and building it before a type holding it."""

from __future__ import annotations

from typing import get_args

from pydantic import BaseModel
from pydantic.dataclasses import is_pydantic_dataclass, rebuild_dataclass

__all__ = ["build_classes_in", "is_unbuilt", "rebuild"]


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


def build_classes_in(type_: object) -> None:
    """Build every class of ``type_``, its arguments included, that pydantic has not built yet.

    A class of a hierarchy is asked for its schema as it builds itself too, and pydantic tells
    that build apart from the others by nothing the class shows: one asked at no field — the
    type itself, or its items — while it is not built yet is read as itself alone. Built first,
    it is read as the hierarchy wherever ``type_`` declares it.
    """
    if isinstance(type_, type) and is_unbuilt(type_):
        rebuild(type_, force=False)
    arguments: tuple[object, ...] = get_args(type_)
    for argument in arguments:
        build_classes_in(argument)
