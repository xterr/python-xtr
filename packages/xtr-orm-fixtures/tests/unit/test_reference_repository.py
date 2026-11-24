"""Unit tests for :class:`xtr_orm_fixtures.ReferenceRepository`."""

from __future__ import annotations

import pytest
import sqlalchemy

from tests.support.models import Group, User
from xtr_orm_fixtures import ReferenceRepository
from xtr_orm_fixtures.exception import ReferenceExistsError, ReferenceNotFoundError


class Note:
    pass


def test_add_reference_refuses_a_taken_name() -> None:
    repository = ReferenceRepository()
    repository.add_reference("first", Note())

    with pytest.raises(ReferenceExistsError) as caught:
        repository.add_reference("first", Note())

    assert (caught.value.name, caught.value.kind) == ("first", "Note")


def test_set_reference_replaces() -> None:
    repository = ReferenceRepository()
    replaced, kept = Note(), Note()
    repository.set_reference("first", replaced)

    repository.set_reference("first", kept)

    assert repository.get_reference("first", Note) is kept


def test_get_reference_of_unknown_name_raises() -> None:
    with pytest.raises(ReferenceNotFoundError) as caught:
        _ = ReferenceRepository().get_reference("first", Note)

    assert (caught.value.name, caught.value.kind) == ("first", "Note")


def test_references_are_kept_per_class() -> None:
    repository = ReferenceRepository()
    user, group = User(name="ada"), Group(name="admins")

    repository.add_reference("admin", user)
    repository.add_reference("admin", group)

    assert repository.get_reference("admin", User) is user
    assert repository.get_reference("admin", Group) is group
    assert repository.has_reference("admin", User)
    assert not repository.has_reference("admin", Note)


def test_mapped_object_is_stored_under_its_mapped_class() -> None:
    repository = ReferenceRepository()
    admin = User(name="ada")
    # Asked for as its type: what its mapper says it loads as.
    mapped = sqlalchemy.inspect(admin).mapper.class_

    repository.add_reference("admin", admin)

    assert repository.get_reference("admin", mapped) is admin
    assert list(repository.references_by_class()) == [User]


def test_the_names_an_object_is_stored_under_are_listed() -> None:
    repository = ReferenceRepository()
    user = User(name="ada")
    repository.add_reference("admin", user)
    repository.add_reference("first", user)
    repository.add_reference("other", User(name="bob"))

    assert repository.get_reference_names(user) == ("admin", "first")


def test_references_by_class_are_read_only_and_as_they_stand() -> None:
    repository = ReferenceRepository()
    note = Note()
    repository.add_reference("first", note)

    references = repository.references_by_class()
    repository.add_reference("second", Note())

    assert dict(references[Note]) == {"first": note}
    with pytest.raises(TypeError):
        references[Note]["third"] = Note()  # pyright: ignore[reportIndexIssue] — a read-only mapping is the case under test  # ty: ignore[invalid-assignment]
