"""The method marking store keeps a subject's marking on the subject itself.

Through the subject's accessors — every test of them runs once with plain
methods and once with coroutines — or, when it has none, through its attribute.
"""

from __future__ import annotations

from typing import assert_never, final

import pytest
from typing_extensions import override

from tests.fixtures.place_enum import PlaceEnum
from tests.fixtures.subject import AsyncSubject, Subject
from tests.fixtures.subject_with_attributes import (
    ChildInheritingAttribute,
    SubjectWithAttributes,
    SubjectWithSlot,
)
from tests.fixtures.subject_with_enum import (
    AsyncSubjectWithEnum,
    SubjectWithEnum,
    SubjectWithEnumAttribute,
    SubjectWithOptionalEnumAttribute,
)
from tests.fixtures.subject_with_unreadable_annotation import SubjectWithUnreadableAnnotation
from tests.fixtures.subject_with_unset_marking import (
    AsyncSubjectWithUnsetMarking,
    SubjectWithUnsetMarking,
)
from xtr_workflow import Marking
from xtr_workflow.exception import LogicError
from xtr_workflow.marking_store import MarkingStoreInterface, MethodMarkingStore

pytestmark = pytest.mark.anyio

ACCESSORS = pytest.mark.parametrize("subject_type", [Subject, AsyncSubject], ids=["sync", "async"])
ENUM_ACCESSORS = pytest.mark.parametrize(
    "subject_type", [SubjectWithEnum, AsyncSubjectWithEnum], ids=["sync", "async"]
)
UNSET_ACCESSORS = pytest.mark.parametrize(
    "subject_type",
    [SubjectWithUnsetMarking, AsyncSubjectWithUnsetMarking],
    ids=["sync", "async"],
)


@final
class _PlaceName:
    """A value object standing for a place, which it names through ``str()``."""

    def __init__(self, name: str) -> None:
        self._name = name

    @override
    def __str__(self) -> str:
        return self._name


async def _kept_by(
    subject: Subject | AsyncSubject | SubjectWithEnum | AsyncSubjectWithEnum,
) -> object:
    """Read what ``subject`` keeps, through its own getter."""
    match subject:
        case Subject() | SubjectWithEnum():
            return subject.get_marking()
        case AsyncSubject() | AsyncSubjectWithEnum():
            return await subject.get_marking()
        case _:
            assert_never(subject)


def test_it_is_a_marking_store() -> None:
    assert MarkingStoreInterface in MethodMarkingStore.__mro__


# Through accessors.


@ACCESSORS
async def test_it_keeps_a_workflow_marking_as_a_dict_of_places(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    subject = subject_type()
    store = MethodMarkingStore(single_state=False)

    marking = await store.get_marking(subject)

    assert marking.get_places() == {}

    marking.mark("first_place")
    await store.set_marking(subject, marking, {"foo": "bar"})

    assert await _kept_by(subject) == {"first_place": 1}
    assert subject.get_context() == {"foo": "bar"}
    assert (await store.get_marking(subject)).get_places() == marking.get_places()


@ACCESSORS
async def test_it_keeps_a_state_machine_marking_as_the_name_of_its_place(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    subject = subject_type()
    store = MethodMarkingStore(single_state=True)

    marking = await store.get_marking(subject)

    assert marking.get_places() == {}

    marking.mark("first_place")
    await store.set_marking(subject, marking, {"foo": "bar"})

    assert await _kept_by(subject) == "first_place"
    assert subject.get_context() == {"foo": "bar"}
    assert (await store.get_marking(subject)).get_places() == marking.get_places()


@ACCESSORS
async def test_a_place_read_as_a_falsy_value_is_still_a_place(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    marking = await MethodMarkingStore(single_state=True).get_marking(subject_type(0))

    assert marking.get_places() == {"0": 1}


@ACCESSORS
async def test_a_value_object_is_read_as_the_place_it_names(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    subject = subject_type(_PlaceName("first_place"))

    marking = await MethodMarkingStore(single_state=True).get_marking(subject)

    assert marking.get_places() == {"first_place": 1}
    assert str(await _kept_by(subject)) == "first_place"


@ENUM_ACCESSORS
async def test_an_enum_member_is_read_as_its_value_and_a_place_written_as_its_member(
    subject_type: type[SubjectWithEnum | AsyncSubjectWithEnum],
) -> None:
    subject = subject_type(PlaceEnum.FOO)
    store = MethodMarkingStore(single_state=True)

    marking = await store.get_marking(subject)

    assert marking.get_places() == {"foo": 1}

    marking.mark("bar")
    marking.unmark("foo")
    await store.set_marking(subject, marking)

    assert await _kept_by(subject) is PlaceEnum.BAR


@UNSET_ACCESSORS
async def test_a_getter_reading_its_unset_attribute_reads_an_empty_marking(
    subject_type: type[SubjectWithUnsetMarking | AsyncSubjectWithUnsetMarking],
) -> None:
    marking = await MethodMarkingStore(single_state=True).get_marking(subject_type())

    assert marking.get_places() == {}


@UNSET_ACCESSORS
async def test_a_getter_reading_an_unset_attribute_of_another_name_raises(
    subject_type: type[SubjectWithUnsetMarking | AsyncSubjectWithUnsetMarking],
) -> None:
    subject = subject_type()
    store = MethodMarkingStore(single_state=True, marking_property="marking2")

    with pytest.raises(AttributeError) as raised:
        _ = await store.get_marking(subject)

    assert raised.value.name == "marking"
    assert raised.value.obj is subject


@UNSET_ACCESSORS
async def test_a_setter_with_no_room_for_the_context_is_handed_the_place_alone(
    subject_type: type[SubjectWithUnsetMarking | AsyncSubjectWithUnsetMarking],
) -> None:
    subject = subject_type()
    store = MethodMarkingStore(single_state=True)

    await store.set_marking(subject, Marking({"first_place": 1}), {"foo": "bar"})

    assert subject.marking == "first_place"


@ACCESSORS
async def test_each_subject_of_a_class_is_read_on_its_own(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    store = MethodMarkingStore(single_state=True)
    subjects = [
        subject_type("first_place"),
        subject_type("second_place"),
        subject_type("third_place"),
    ]

    markings = [await store.get_marking(subject) for subject in subjects]

    assert [marking.get_places() for marking in markings] == [
        {"first_place": 1},
        {"second_place": 1},
        {"third_place": 1},
    ]


@ACCESSORS
async def test_each_subject_of_a_class_is_written_on_its_own(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    store = MethodMarkingStore(single_state=True)
    subjects = [subject_type(), subject_type(), subject_type()]

    for number, subject in enumerate(subjects, start=1):
        marking = await store.get_marking(subject)
        marking.mark(f"place{number}")
        await store.set_marking(subject, marking, {f"context{number}": f"value{number}"})

    assert [await _kept_by(subject) for subject in subjects] == ["place1", "place2", "place3"]
    assert [subject.get_context() for subject in subjects] == [
        {"context1": "value1"},
        {"context2": "value2"},
        {"context3": "value3"},
    ]


@ACCESSORS
async def test_each_subject_of_a_class_is_written_on_its_own_in_a_workflow(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    store = MethodMarkingStore(single_state=False)
    first, second = subject_type(), subject_type()

    first_marking = await store.get_marking(first)
    first_marking.mark("place1")
    first_marking.mark("place2")
    await store.set_marking(first, first_marking, {"context1": "value1"})
    second_marking = await store.get_marking(second)
    second_marking.mark("place3")
    await store.set_marking(second, second_marking, {"context2": "value2"})

    assert await _kept_by(first) == {"place1": 1, "place2": 1}
    assert first.get_context() == {"context1": "value1"}
    assert await _kept_by(second) == {"place3": 1}
    assert second.get_context() == {"context2": "value2"}


@ACCESSORS
async def test_a_workflow_marking_kept_as_anything_but_a_dict_is_refused(
    subject_type: type[Subject | AsyncSubject],
) -> None:
    with pytest.raises(LogicError) as raised:
        _ = await MethodMarkingStore(single_state=False).get_marking(subject_type("first_place"))

    assert str(raised.value) == (
        f'The marking stored in "{subject_type.__name__}.marking" is not a dict and the '
        "Workflow's Marking store is instantiated with single_state=False."
    )


# Through an attribute.


async def test_it_keeps_a_workflow_marking_in_an_attribute() -> None:
    subject = SubjectWithAttributes()
    store = MethodMarkingStore(single_state=False)

    marking = await store.get_marking(subject)

    assert marking.get_places() == {}

    marking.mark("first_place")
    await store.set_marking(subject, marking, {"foo": "bar"})

    assert subject.marking == {"first_place": 1}
    assert (await store.get_marking(subject)).get_places() == marking.get_places()


async def test_it_keeps_a_state_machine_marking_in_an_attribute() -> None:
    subject = SubjectWithAttributes()
    store = MethodMarkingStore(single_state=True, marking_property="place")

    marking = await store.get_marking(subject)

    assert marking.get_places() == {}

    marking.mark("first_place")
    await store.set_marking(subject, marking, {"foo": "bar"})

    assert subject.place == "first_place"
    assert (await store.get_marking(subject)).get_places() == marking.get_places()


async def test_an_attribute_holding_a_falsy_value_is_still_a_place() -> None:
    subject = SubjectWithAttributes()
    subject.place = 0

    marking = await MethodMarkingStore(single_state=True, marking_property="place").get_marking(
        subject
    )

    assert marking.get_places() == {"0": 1}


async def test_an_attribute_holding_a_value_object_is_read_as_the_place_it_names() -> None:
    subject = SubjectWithAttributes()
    subject.place = _PlaceName("first_place")

    marking = await MethodMarkingStore(single_state=True, marking_property="place").get_marking(
        subject
    )

    assert marking.get_places() == {"first_place": 1}
    assert str(subject.place) == "first_place"


async def test_an_unset_attribute_reads_an_empty_marking() -> None:
    marking = await MethodMarkingStore(single_state=True, marking_property="place").get_marking(
        SubjectWithAttributes()
    )

    assert marking.get_places() == {}


async def test_an_unset_inherited_attribute_reads_an_empty_marking() -> None:
    marking = await MethodMarkingStore(single_state=True, marking_property="place").get_marking(
        ChildInheritingAttribute()
    )

    assert marking.get_places() == {}


async def test_an_unset_slot_reads_an_empty_marking_until_it_is_written() -> None:
    subject = SubjectWithSlot()
    store = MethodMarkingStore(single_state=False)

    marking = await store.get_marking(subject)

    assert marking.get_places() == {}

    marking.mark("first_place")
    await store.set_marking(subject, marking)

    assert (await store.get_marking(subject)).get_places() == {"first_place": 1}


async def test_each_subject_of_a_class_is_written_on_its_own_attribute_in_a_workflow() -> None:
    store = MethodMarkingStore(single_state=False)
    subjects = [SubjectWithAttributes(), SubjectWithAttributes(), SubjectWithAttributes()]

    for number, subject in enumerate(subjects, start=1):
        marking = await store.get_marking(subject)
        marking.mark(f"place{number}")
        await store.set_marking(subject, marking, {f"context{number}": f"value{number}"})

    assert [subject.marking for subject in subjects] == [
        {"place1": 1},
        {"place2": 1},
        {"place3": 1},
    ]


async def test_each_subject_of_a_class_is_written_on_its_own_attribute_in_a_state_machine() -> None:
    store = MethodMarkingStore(single_state=True, marking_property="place")
    first, second = SubjectWithAttributes(), SubjectWithAttributes()

    first_marking = await store.get_marking(first)
    first_marking.mark("place1")
    await store.set_marking(first, first_marking, {"context1": "value1"})
    second_marking = await store.get_marking(second)
    second_marking.mark("place2")
    await store.set_marking(second, second_marking, {"context2": "value2"})

    assert first.place == "place1"
    assert second.place == "place2"


async def test_an_attribute_annotated_with_an_enum_is_set_to_its_member() -> None:
    subject = SubjectWithEnumAttribute()
    store = MethodMarkingStore(single_state=True)

    await store.set_marking(subject, Marking({"bar": 1}))

    assert subject.marking is PlaceEnum.BAR
    assert (await store.get_marking(subject)).get_places() == {"bar": 1}


async def test_an_attribute_annotated_with_an_optional_enum_is_set_to_its_member() -> None:
    subject = SubjectWithOptionalEnumAttribute()

    await MethodMarkingStore(single_state=True).set_marking(subject, Marking({"bar": 1}))

    assert subject.marking is PlaceEnum.BAR


async def test_an_annotation_evaluated_with_its_class_is_read_as_it_is() -> None:
    @final
    class EvaluatedSubject:
        marking: PlaceEnum | None = None

    # What code that does not postpone its annotations holds: the type, not its source.
    EvaluatedSubject.__annotations__["marking"] = PlaceEnum
    subject = EvaluatedSubject()

    await MethodMarkingStore(single_state=True).set_marking(subject, Marking({"foo": 1}))

    assert subject.marking is PlaceEnum.FOO


# Neither.


async def test_a_subject_with_neither_accessor_nor_attribute_is_refused() -> None:
    with pytest.raises(LogicError) as raised:
        _ = await MethodMarkingStore().get_marking(object())

    assert str(raised.value) == (
        'Cannot store marking: class "object" should have either a public method named '
        '"get_marking()" or a public property named "marking"; none found.'
    )


async def test_a_setter_annotated_with_what_only_the_type_checker_imports_is_refused() -> None:
    store = MethodMarkingStore(single_state=True)

    with pytest.raises(LogicError) as raised:
        await store.set_marking(SubjectWithUnreadableAnnotation(), Marking({"foo": 1}))

    assert str(raised.value) == (
        "Cannot store marking: the annotation of the first parameter of "
        '"SubjectWithUnreadableAnnotation.set_marking()" cannot be read at runtime '
        "(name 'PlaceEnum' is not defined); import what it names outside TYPE_CHECKING."
    )


async def test_a_workflow_setter_is_handed_its_places_without_its_annotation_being_read() -> None:
    subject = SubjectWithUnreadableAnnotation()

    await MethodMarkingStore(single_state=False).set_marking(subject, Marking({"foo": 1}))

    assert subject.get_marking() == {"foo": 1}
