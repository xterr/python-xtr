"""A factory written at registration takes its parameters by keyword and builds from them."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

from xtr_workflow.bundle._injecting_factory import injecting_factory

if TYPE_CHECKING:
    from collections.abc import Mapping


def _joined(arguments: Mapping[str, object]) -> str:
    return ",".join(f"{name}={value}" for name, value in arguments.items())


def test_the_factory_declares_each_parameter_by_keyword_and_its_return_type() -> None:
    factory = injecting_factory(_joined, {"first": int, "second": str}, str)

    signature = inspect.signature(factory)

    assert [
        (p.name, p.kind, cast("object", p.annotation)) for p in signature.parameters.values()
    ] == [
        ("first", inspect.Parameter.KEYWORD_ONLY, int),
        ("second", inspect.Parameter.KEYWORD_ONLY, str),
    ]
    assert cast("object", signature.return_annotation) is str
    assert factory.__annotations__ == {"first": int, "second": str, "return": str}


def test_the_factory_hands_its_arguments_to_the_builder_by_name() -> None:
    factory = injecting_factory(_joined, {"first": int, "second": str}, str)

    assert factory(first=1, second="b") == "first=1,second=b"
