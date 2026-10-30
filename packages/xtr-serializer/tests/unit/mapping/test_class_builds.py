"""Classes pydantic builds itself, told built or not, and built again."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

from xtr_serializer.mapping._class_builds import is_unbuilt, rebuild


class Deferred(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)


class Built(BaseModel):
    pass


@dataclass
class Plain:
    pass


def deferred_dataclass() -> type[object]:
    @pydantic_dataclass(config=ConfigDict(defer_build=True))
    class Later:
        pass

    return Later


def test_only_a_class_pydantic_builds_and_has_not_built_is_unbuilt() -> None:
    later = deferred_dataclass()

    assert [is_unbuilt(kind) for kind in (Deferred, later, Built, Plain)] == [
        True,
        True,
        False,
        False,
    ]


def test_a_subclass_of_a_built_class_is_unbuilt_until_built_itself() -> None:
    class Sub(Built):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

    assert is_unbuilt(Sub)


def test_rebuilding_builds_models_and_pydantic_dataclasses() -> None:
    class Model(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

    later = deferred_dataclass()

    for kind in (Model, later, Plain):
        rebuild(kind, force=False)

    assert not is_unbuilt(Model)
    assert not is_unbuilt(later)
