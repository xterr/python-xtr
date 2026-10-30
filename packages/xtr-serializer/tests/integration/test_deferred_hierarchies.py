"""Hierarchies of classes pydantic has not built yet, read wherever a type holds them."""

from __future__ import annotations

import operator
from dataclasses import field
from functools import partial
from sys import getswitchinterval, setswitchinterval
from threading import Barrier, Thread
from typing import TYPE_CHECKING, Annotated, ClassVar, NewType, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing_extensions import TypeAliasType

from xtr_serializer import (
    NotNormalizableValueError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

_DEFERRED = ConfigDict(defer_build=True)
_POST: dict[str, object] = {"$type": "post", "body": "b"}
_FORGED = ("FORGED", "POST", "Post", " post", "post ", "post\n")

# Types built at run time from a class known then, which type checkers read as no type at all.
_alias = cast("Callable[[str, object], object]", TypeAliasType)
_new_type = cast("Callable[[str, object], object]", NewType)
# ``X | Y`` of an alias or a new type is ``Union[X, Y]``, and ``X | None`` is ``Optional[X]``.
_union = cast("Callable[[object, object], object]", operator.or_)


def subscribed(form: object, *arguments: object) -> object:
    """Give ``form[arguments]``, a generic or a special form subscribed at run time."""
    return operator.getitem(
        cast("dict[object, object]", form), arguments[0] if len(arguments) == 1 else arguments
    )


Kinds = tuple["type[object]", "type[object]"]


def model_hierarchy() -> Kinds:
    """A thread holding its replies, and a post, as models pydantic has not built."""

    @discriminator_name("thread")
    @discriminator_map()
    class Topic(BaseModel):
        model_config: ClassVar[ConfigDict] = _DEFERRED

        replies: list[Topic] = Field(default_factory=list["Topic"])

    @discriminator_name("post")
    class Post(Topic):
        body: str

    return Topic, Post


def dataclass_hierarchy() -> Kinds:
    """The same, as pydantic dataclasses pydantic has not built."""

    @discriminator_name("thread")
    @discriminator_map()
    @pydantic_dataclass(config=_DEFERRED)
    class Topic:
        replies: list[Topic] = field(default_factory=list["Topic"])

    @discriminator_name("post")
    @pydantic_dataclass(config=_DEFERRED)
    class Post(Topic):
        body: str = ""

    return Topic, Post


def build(kinds: Kinds) -> None:
    """Build the classes as pydantic does on their first use: by making a value of each."""
    topic, post = kinds
    _ = topic()
    _ = cast("Callable[..., object]", post)(body="b")


def first(read: object) -> object:
    return cast("list[object]", read)[0]


def itself(read: object) -> object:
    return read


# Each place a type may hold the base at no field: the type made of it, and where the post is.
_ENTRY_POINTS: dict[str, tuple[Callable[[type[object]], object], Callable[[object], object]]] = {
    "alias of a list": (lambda base: _alias("Replies", subscribed(list, base)), first),
    "new type": (lambda base: _new_type("Head", base), itself),
    "annotated alias": (
        lambda base: subscribed(
            Annotated, _alias("One", base), cast("object", Field(description="one"))
        ),
        itself,
    ),
    "list of an alias": (lambda base: subscribed(list, _alias("One", base)), first),
    "optional new type": (lambda base: _union(_new_type("Head", base), None), itself),
    "union of an alias": (lambda base: _union(_alias("One", base), int), itself),
    "alias of an alias": (lambda base: _alias("Outer", _alias("Inner", base)), itself),
}

_HIERARCHIES = {"model": model_hierarchy, "pydantic dataclass": dataclass_hierarchy}


def made(entry: str, hierarchy: str, *, built: bool) -> tuple[Kinds, object]:
    """Make a hierarchy, built or not, and the type holding its base at ``entry``."""
    kinds = _HIERARCHIES[hierarchy]()
    if built:
        build(kinds)
    return kinds, _ENTRY_POINTS[entry][0](kinds[0])


def data_at(entry: str, value: dict[str, object]) -> object:
    """Give ``value`` where the type made at ``entry`` holds it."""
    return [value] if _ENTRY_POINTS[entry][1] is first else value


@pytest.mark.parametrize("built", [False, True], ids=["unbuilt", "built"])
@pytest.mark.parametrize("hierarchy", list(_HIERARCHIES))
@pytest.mark.parametrize("entry", list(_ENTRY_POINTS))
def test_a_class_held_at_no_field_reads_the_class_named(
    entry: str, hierarchy: str, *, built: bool
) -> None:
    kinds, type_ = made(entry, hierarchy, built=built)

    read = PydanticNormalizer().denormalize(data_at(entry, _POST), type_)

    assert type(_ENTRY_POINTS[entry][1](read)) is kinds[1]


@pytest.mark.parametrize("built", [False, True], ids=["unbuilt", "built"])
@pytest.mark.parametrize("hierarchy", list(_HIERARCHIES))
@pytest.mark.parametrize("entry", list(_ENTRY_POINTS))
def test_a_class_held_at_no_field_refuses_a_name_it_does_not_know(
    entry: str, hierarchy: str, *, built: bool
) -> None:
    _, type_ = made(entry, hierarchy, built=built)
    normalizer = PydanticNormalizer()

    error_types: list[str | None] = []
    for tag in _FORGED:
        with pytest.raises(NotNormalizableValueError) as caught:
            _ = normalizer.denormalize(data_at(entry, {**_POST, "$type": tag}), type_)
        error_types.append(caught.value.error_type)

    assert set(error_types) == {"class_discriminator"}


def test_a_class_read_at_no_field_still_builds_and_validates_as_itself() -> None:
    topic, post = model_hierarchy()
    _ = PydanticNormalizer().denormalize([_POST], _alias("Replies", subscribed(list, topic)))

    value = cast("Callable[..., BaseModel]", topic)(
        replies=[cast("Callable[..., object]", post)(body="b")]
    )

    assert type(value.model_dump(round_trip=True)) is dict
    assert type(cast("type[BaseModel]", topic).model_validate({"replies": [_POST]})) is topic


# How many threads use one normalizer first at once, and how many times, each a fresh class.
_THREADS = 12
_TRIALS = 30


@pytest.fixture
def switching_often() -> Iterator[None]:
    """Have the interpreter switch threads as often as it can, so that their steps interleave."""
    interval = getswitchinterval()
    setswitchinterval(1e-6)
    yield
    setswitchinterval(interval)


def plain_deferred() -> Kinds:
    """A deferred model holding another, in no hierarchy."""

    class Leaf(BaseModel):
        model_config: ClassVar[ConfigDict] = _DEFERRED

        body: str

    class Tree(BaseModel):
        model_config: ClassVar[ConfigDict] = _DEFERRED

        leaves: list[Leaf]

    return Tree, Leaf


def at_once(actions: Sequence[Callable[[], object]]) -> list[object]:
    """Run each action on a thread of its own, all released at once; give what each did."""
    barrier = Barrier(len(actions))
    outcomes: list[object] = [None] * len(actions)

    def run(index: int) -> None:
        _ = barrier.wait()
        try:
            outcomes[index] = actions[index]()
        except Exception as error:  # noqa: BLE001 - every outcome is checked, a raised one too
            outcomes[index] = error

    threads = [Thread(target=run, args=(index,)) for index in range(len(actions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes


def kept_refusal(normalizer: PydanticNormalizer, data: object, type_: object) -> list[str]:
    """Say so when ``normalizer`` kept a refusal for ``type_``."""
    supported = normalizer.supports_denormalization(data, type_)
    return [] if supported else ["a refusal was kept"]


@pytest.mark.usefixtures("switching_often")
@pytest.mark.parametrize("hierarchy", list(_HIERARCHIES))
def test_a_hierarchy_used_first_from_many_threads_reads_every_value_right(hierarchy: str) -> None:
    wrong: list[object] = []
    for _ in range(_TRIALS):
        topic, post = _HIERARCHIES[hierarchy]()
        type_ = subscribed(list, topic)
        normalizer = PydanticNormalizer()

        outcomes = at_once([partial(normalizer.denormalize, [_POST], type_)] * _THREADS)

        wrong.extend(each for each in outcomes if not listing(each, post))
        wrong.extend(kept_refusal(normalizer, [_POST], type_))

    assert wrong == []


@pytest.mark.usefixtures("switching_often")
def test_a_deferred_model_used_first_from_many_threads_reads_every_value_right() -> None:
    data = {"leaves": [{"body": "b"}]}
    wrong: list[object] = []
    for _ in range(_TRIALS):
        tree, leaf = plain_deferred()
        normalizer = PydanticNormalizer()

        outcomes = at_once([partial(normalizer.denormalize, data, tree)] * _THREADS)

        wrong.extend(
            each
            for each in outcomes
            if type(each) is not tree or not listing(cast("object", vars(each)["leaves"]), leaf)
        )
        wrong.extend(kept_refusal(normalizer, data, tree))

    assert wrong == []


@pytest.mark.usefixtures("switching_often")
def test_a_hierarchy_read_while_pydantic_builds_it_on_another_thread_reads_the_class_named() -> (
    None
):
    wrong: list[object] = []
    for _ in range(_TRIALS):
        kinds = model_hierarchy()
        topic, post = kinds
        normalizer = PydanticNormalizer()
        reads = [partial(normalizer.denormalize, _POST, topic)] * _THREADS

        *outcomes, built = at_once([*reads, partial(build, kinds)])

        wrong.extend(each for each in outcomes if type(each) is not post)
        wrong.extend([] if built is None else [built])
        wrong.extend(kept_refusal(normalizer, _POST, topic))

    assert wrong == []


def listing(outcome: object, kind: type[object]) -> bool:
    """Whether ``outcome`` is a list of one value, of ``kind`` exactly."""
    return type(outcome) is list and [type(each) for each in cast("list[object]", outcome)] == [
        kind
    ]
