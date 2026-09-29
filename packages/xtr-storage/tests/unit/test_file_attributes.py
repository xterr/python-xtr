from __future__ import annotations

import dataclasses

import pytest

from xtr_storage.file_attributes import FileAttributes
from xtr_storage.visibility import Visibility


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_a_path_keeps_what_it_was_given() -> None:
    assert FileAttributes("some/file.txt").path == "some/file.txt"


def test_a_leading_slash_is_dropped() -> None:
    assert FileAttributes("/some/file.txt").path == "some/file.txt"


def test_every_leading_slash_is_dropped() -> None:
    assert FileAttributes("///some/file.txt").path == "some/file.txt"


def test_a_trailing_slash_is_left_alone() -> None:
    assert FileAttributes("odd.name/").path == "odd.name/"


def test_the_type_is_file() -> None:
    assert FileAttributes("a.txt").type == "file"


def test_a_file_is_a_file() -> None:
    assert FileAttributes("a.txt").is_file is True


def test_a_file_is_not_a_directory() -> None:
    assert FileAttributes("a.txt").is_dir is False


def test_what_the_backend_did_not_say_is_none() -> None:
    attributes = FileAttributes("a.txt")

    assert (
        attributes.file_size,
        attributes.visibility,
        attributes.last_modified,
        attributes.mime_type,
    ) == (None, None, None, None)


def test_there_is_no_extra_metadata_unless_the_backend_gave_some() -> None:
    assert FileAttributes("a.txt").extra_metadata == {}


def test_two_files_do_not_share_their_extra_metadata() -> None:
    assert FileAttributes("a.txt").extra_metadata is not FileAttributes("b.txt").extra_metadata


def test_nothing_can_be_changed_after_the_fact() -> None:
    attributes = FileAttributes("a.txt")

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(attributes, "path", "b.txt")


def test_with_path_moves_the_description_to_another_path() -> None:
    assert FileAttributes("inner/a.txt").with_path("outer/a.txt").path == "outer/a.txt"


def test_with_path_keeps_everything_the_backend_said() -> None:
    attributes = FileAttributes(
        "inner/a.txt",
        file_size=12,
        visibility=Visibility.PUBLIC,
        last_modified=1_700_000_000,
        mime_type="text/plain",
        extra_metadata={"etag": "abc"},
    )

    moved = attributes.with_path("outer/a.txt")

    assert (moved.file_size, moved.visibility, moved.last_modified, moved.mime_type) == (
        12,
        Visibility.PUBLIC,
        1_700_000_000,
        "text/plain",
    )


def test_with_path_drops_a_leading_slash_from_the_new_path() -> None:
    assert FileAttributes("a.txt").with_path("/b.txt").path == "b.txt"


def test_with_path_leaves_the_description_it_was_called_on_alone() -> None:
    attributes = FileAttributes("a.txt")

    _ = attributes.with_path("b.txt")

    assert attributes.path == "a.txt"


def test_to_dict_carries_every_field_under_its_name() -> None:
    attributes = FileAttributes(
        "a.txt",
        file_size=12,
        visibility=Visibility.PRIVATE,
        last_modified=1_700_000_000,
        mime_type="text/plain",
        extra_metadata={"etag": "abc"},
    )

    assert attributes.to_dict() == {
        "type": "file",
        "path": "a.txt",
        "file_size": 12,
        "visibility": Visibility.PRIVATE,
        "last_modified": 1_700_000_000,
        "mime_type": "text/plain",
        "extra_metadata": {"etag": "abc"},
    }


def test_to_dict_of_a_bare_file_still_names_every_field() -> None:
    assert set(FileAttributes("a.txt").to_dict()) == {
        "type",
        "path",
        "file_size",
        "visibility",
        "last_modified",
        "mime_type",
        "extra_metadata",
    }


def test_two_descriptions_of_the_same_file_are_equal() -> None:
    assert FileAttributes("/a.txt", file_size=1) == FileAttributes("a.txt", file_size=1)
