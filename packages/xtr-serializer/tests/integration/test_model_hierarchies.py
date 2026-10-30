"""Hierarchies of models and pydantic dataclasses, which pydantic builds and validates itself."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

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


def test_a_model_not_built_yet_is_read_as_itself_in_a_type_built_before_it() -> None:
    @discriminator_name("draft")
    @discriminator_map()
    class Draft(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

    @discriminator_name("revision")
    class Revision(Draft):
        number: int

    class Folder(BaseModel):
        drafts: list[Draft]

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(Folder(drafts=[Revision(number=1)]))

    assert (caught.value.path, caught.value.error_type) == ("drafts[0]", "not_exact")


def test_plain_pydantic_also_carries_the_class_names() -> None:
    adapter = TypeAdapter(list[Notice])
    notices = [Reminder(title="t", due=AT), Notice(title="n")]

    assert adapter.validate_json(adapter.dump_json(notices)) == notices
