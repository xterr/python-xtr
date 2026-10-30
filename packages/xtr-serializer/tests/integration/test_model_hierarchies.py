"""Hierarchies of models and pydantic dataclasses, which pydantic builds and validates itself."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from pydantic.dataclasses import dataclass as pydantic_dataclass

from tests.fixtures.hierarchies import (
    Board,
    Circle,
    Drawing,
    Notice,
    Outage,
    Reminder,
    Square,
)
from xtr_serializer import (
    ALLOW_EXTRA_ATTRIBUTES,
    JsonEncoder,
    NotNormalizableValueError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)

AT = datetime(2026, 10, 30, 9, 30, tzinfo=UTC)
NORMALIZER = PydanticNormalizer()
ENCODER = JsonEncoder()


def round_trip(value: object) -> object:
    data = ENCODER.decode(ENCODER.encode(NORMALIZER.normalize(value), "json"), "json")
    return NORMALIZER.denormalize(data, type(value))


def test_models_of_a_hierarchy_read_back_as_their_exact_class() -> None:
    board = Board(
        pinned=Reminder(title="pay", due=AT),
        alerts=[Outage(title="down", level=2, region="eu")],
        archive=(Notice(title="hello"), Outage(title="up", level=0, region="us")),
    )

    read = cast("Board", round_trip(board))

    assert read == board
    assert [type(notice) for notice in read.archive] == [Notice, Outage]
    assert cast("dict[str, object]", NORMALIZER.normalize(board))["pinned"] == {
        "$type": "reminder",
        "title": "pay",
        "due": "2026-10-30T09:30:00Z",
    }


def test_a_model_of_a_hierarchy_is_still_built_and_validated_as_itself() -> None:
    reminder = Reminder(title="pay", due=AT)

    assert reminder.model_fields_set == {"title", "due"}
    assert (
        Reminder.model_validate_json('{"title": "pay", "due": "2026-10-30T09:30:00Z"}') == reminder
    )
    assert reminder.model_dump() == {"title": "pay", "due": AT}
    assert vars(Reminder.model_validate_json(Reminder(title="x", due=AT).model_dump_json())) == {
        "title": "x",
        "due": AT,
    }


def test_a_model_closed_to_other_fields_reads_its_class_name_all_the_same() -> None:
    data = {"$type": "outage", "title": "down", "level": 1, "region": "eu"}

    read = NORMALIZER.denormalize(data, Notice, context={ALLOW_EXTRA_ATTRIBUTES: False})

    assert read == Outage(title="down", level=1, region="eu")
    assert read.model_fields_set == {"title", "level", "region"}


def test_pydantic_dataclasses_of_a_hierarchy_read_back_as_their_exact_class() -> None:
    drawing = Drawing([Circle("c", 1.5), Square("s", 2.0)])

    read = cast("Drawing", round_trip(drawing))

    assert read == drawing
    assert [type(shape) for shape in read.shapes] == [Circle, Square]
    assert Circle("c", 1.5) == Circle(label="c", radius=1.5)
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.denormalize(
            {"shapes": [{"$type": "circle", "label": "c", "radius": "1"}]}, Drawing
        )
    assert caught.value.path == "shapes[0].radius"


def test_a_model_holding_its_own_hierarchy_is_built_once_its_classes_are_named() -> None:
    @discriminator_name("thread")
    @discriminator_map()
    class Thread(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True, strict=True)

        replies: list[Thread] = Field(default_factory=list["Thread"])
        quoted: Thread | None = None

    @discriminator_name("post")
    class Post(Thread):
        body: str

    thread = Thread(replies=[Post(body="hi"), Thread()], quoted=Post(body="q"))

    read = cast("Thread", round_trip(thread))

    assert read == thread
    assert [type(reply) for reply in read.replies] == [Post, Thread]


def test_plain_pydantic_also_carries_the_class_names() -> None:
    adapter = TypeAdapter(list[Notice])
    notices = [Reminder(title="t", due=AT), Notice(title="n")]

    assert adapter.validate_json(adapter.dump_json(notices)) == notices


def test_a_model_holding_its_own_class_built_before_it_is_named_refuses_what_it_holds() -> None:
    @discriminator_name("early")
    @discriminator_map()
    class Early(BaseModel):
        replies: list[Early] = Field(default_factory=list["Early"])

    assert Early() == Early(replies=[])
    with pytest.raises(ValidationError):
        _ = Early(replies=[Early()])
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(Early.model_construct(replies=[Early()]))
    assert caught.value.error_type == "class_discriminator_unnamed"


def test_a_deferred_model_read_before_its_first_use_reads_the_class_named() -> None:
    @discriminator_name("topic")
    @discriminator_map()
    class Topic(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

        replies: list[Topic] = Field(default_factory=list["Topic"])

    @discriminator_name("answer")
    class Answer(Topic):
        body: str

    read = PydanticNormalizer().denormalize({"$type": "answer", "body": "b", "replies": []}, Topic)

    assert type(read) is Answer
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = PydanticNormalizer().denormalize({"$type": "FORGED", "replies": []}, Topic)
    assert caught.value.error_type == "class_discriminator"


def test_a_model_holding_a_deferred_model_reads_the_class_named() -> None:
    @discriminator_name("topic")
    @discriminator_map()
    class Topic(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

        replies: list[Topic] = Field(default_factory=list["Topic"])

    @discriminator_name("answer")
    class Answer(Topic):
        body: str

    class Forum(BaseModel):
        top: Topic

    data = {"top": {"$type": "answer", "body": "b", "replies": [{"$type": "topic"}]}}

    read = NORMALIZER.denormalize(data, Forum, context={ALLOW_EXTRA_ATTRIBUTES: False})

    assert read == Forum(top=Answer(body="b", replies=[Topic()]))
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.denormalize({"top": {"$type": "FORGED", "replies": []}}, Forum)
    assert (caught.value.path, caught.value.error_type) == ("top", "class_discriminator")


def test_models_checking_their_data_first_are_read_without_the_class_name() -> None:
    seen: list[object] = []

    @discriminator_map()
    class Checked(BaseModel):
        count: int = 0

        @model_validator(mode="before")
        @classmethod
        def remember(cls, data: object) -> object:
            seen.append(data)
            return data

    @discriminator_name("checked_more")
    class CheckedMore(Checked):
        @model_validator(mode="before")
        @classmethod
        def remember_too(cls, data: object) -> object:
            seen.append(data)
            return data

    read = NORMALIZER.denormalize({"$type": "checked_more", "count": 1}, Checked)

    assert seen == [{"count": 1}, {"count": 1}]
    assert read == CheckedMore(count=1)


def test_pydantic_dataclasses_checking_their_data_first_are_read_without_the_class_name() -> None:
    seen: list[object] = []

    @discriminator_map()
    @pydantic_dataclass
    class Checked:
        count: int = 0

        @model_validator(mode="before")
        @classmethod
        def remember(cls, data: object) -> object:
            seen.append(data)
            return data

    @discriminator_name("checked_more")
    @pydantic_dataclass
    class CheckedMore(Checked):
        pass

    read = NORMALIZER.denormalize({"$type": "checked_more", "count": 1}, Checked)

    assert seen == [{"count": 1}]
    assert read == CheckedMore(1)
