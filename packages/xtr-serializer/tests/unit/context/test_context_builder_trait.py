"""Every context builder starts from a copy and hands back a copy, so no caller can change it."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import TYPE_CHECKING, NamedTuple, TypeAlias, cast

import pytest

from xtr_serializer import (
    ATTRIBUTES,
    JSON_INDENT,
    InvalidArgumentError,
    JsonEncoderContextBuilder,
    PydanticNormalizerContextBuilder,
    SerializerContextBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context, ContextBuilderInterface

_Build: TypeAlias = "Callable[[Context | None], ContextBuilderInterface]"

_BUILDERS = [
    pytest.param(SerializerContextBuilder, id="serializer"),
    pytest.param(PydanticNormalizerContextBuilder, id="pydantic-normalizer"),
    pytest.param(JsonEncoderContextBuilder, id="json-encoder"),
]


class Bounds(NamedTuple):
    """What a validator reads by name from the context."""

    low: int
    high: int


class Tags(list[str]):
    """A list of a type of its own."""


def nested_lists(depth: int) -> list[object]:
    root: list[object] = []
    current = root
    for _ in range(depth - 1):
        child: list[object] = []
        current.append(child)
        current = child
    return root


@pytest.mark.parametrize("build", _BUILDERS)
def test_it_starts_with_no_options(build: _Build) -> None:
    assert build(None).to_dict() == {}


@pytest.mark.parametrize("build", _BUILDERS)
def test_it_starts_from_the_context_it_is_given(build: _Build) -> None:
    assert build({JSON_INDENT: 2}).to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    start: dict[str, object] = {JSON_INDENT: 2}
    builder = build(start)

    start[JSON_INDENT] = 4

    assert builder.to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_a_set_in_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    names = {"a"}
    builder = build({ATTRIBUTES: names})

    names.add("x")

    assert builder.to_dict() == {ATTRIBUTES: {"a"}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_deep_inside_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    tags = ["a"]
    builder = build({"labels": {"tags": (tags,)}})

    tags.append("x")

    assert builder.to_dict() == {"labels": {"tags": (["a"],)}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_the_dictionary_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({JSON_INDENT: 2})
    context = builder.to_dict()

    context[JSON_INDENT] = 4

    assert builder.to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_a_set_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({ATTRIBUTES: {"a"}})
    names = cast("set[str]", builder.to_dict()[ATTRIBUTES])

    names.add("x")

    assert builder.to_dict() == {ATTRIBUTES: {"a"}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_deep_inside_the_dictionary_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({"labels": {"tags": (["a"],)}})
    labels = cast("dict[str, tuple[list[str]]]", builder.to_dict()["labels"])

    labels["tags"][0].append("x")

    assert builder.to_dict() == {"labels": {"tags": (["a"],)}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_an_object_in_that_context_is_handed_on_as_it_is(build: _Build) -> None:
    repository = object()

    handed_on = build({"repository": repository}).to_dict()["repository"]

    assert handed_on is repository


@pytest.mark.parametrize(
    "value",
    [Bounds(1, 9), defaultdict(list, {"a": [1]}), OrderedDict({"a": 1}), Tags(["a"])],
    ids=["named-tuple", "default-dict", "ordered-dict", "list-subclass"],
)
@pytest.mark.parametrize("build", _BUILDERS)
def test_a_subclass_of_a_type_it_copies_is_handed_on_as_it_is(build: _Build, value: object) -> None:
    handed_on = build({"value": value}).to_dict()["value"]

    assert handed_on is value


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_dictionary_that_holds_itself_is_copied_holding_its_copy(build: _Build) -> None:
    looped: dict[str, object] = {}
    looped["self"] = looped

    copied = cast("dict[str, object]", build({"looped": looped}).to_dict()["looped"])

    assert copied is not looped
    assert copied["self"] is copied


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_tuple_holding_a_list_that_holds_it_is_copied_once(build: _Build) -> None:
    looped: list[object] = []
    pair = (looped,)
    looped.append(pair)

    copied = cast("tuple[list[object]]", build({"pair": pair}).to_dict()["pair"])

    assert copied is not pair
    assert copied[0][0] is copied


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_context_that_holds_itself_is_copied_holding_its_copy(build: _Build) -> None:
    context: dict[str, object] = {}
    context["self"] = context

    copied = build(context).to_dict()

    assert copied["self"] is copied


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_list_held_twice_is_copied_once(build: _Build) -> None:
    tags = ["a"]

    copied = build({"first": tags, "second": tags}).to_dict()

    assert copied["first"] is copied["second"]
    assert copied["first"] is not tags


@pytest.mark.parametrize("build", _BUILDERS)
def test_it_copies_a_context_nested_as_deep_as_it_copies(build: _Build) -> None:
    nested = nested_lists(100)

    assert build({"nested": nested}).to_dict() == {"nested": nested}


@pytest.mark.parametrize("depth", [101, 5000])
@pytest.mark.parametrize("build", _BUILDERS)
def test_it_refuses_a_context_nested_deeper_than_it_copies(build: _Build, depth: int) -> None:
    with pytest.raises(InvalidArgumentError, match="more than 100 levels deep"):
        _ = build({"nested": nested_lists(depth)})
