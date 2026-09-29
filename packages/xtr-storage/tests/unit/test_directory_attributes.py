from __future__ import annotations

import dataclasses

import pytest

from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.visibility import Visibility


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_a_path_keeps_what_it_was_given() -> None:
    assert DirectoryAttributes("some/dir").path == "some/dir"


def test_a_leading_slash_is_dropped() -> None:
    assert DirectoryAttributes("/some/dir").path == "some/dir"


def test_a_trailing_slash_is_dropped() -> None:
    assert DirectoryAttributes("some/dir/").path == "some/dir"


def test_a_backend_naming_a_directory_with_slashes_describes_the_same_place() -> None:
    assert DirectoryAttributes("/some/dir/") == DirectoryAttributes("some/dir")


def test_the_root_of_a_storage_is_the_empty_path() -> None:
    assert DirectoryAttributes("/").path == ""


def test_the_type_is_dir() -> None:
    assert DirectoryAttributes("some/dir").type == "dir"


def test_a_directory_is_not_a_file() -> None:
    assert DirectoryAttributes("some/dir").is_file is False


def test_a_directory_is_a_directory() -> None:
    assert DirectoryAttributes("some/dir").is_dir is True


def test_what_the_backend_did_not_say_is_none() -> None:
    attributes = DirectoryAttributes("some/dir")

    assert (attributes.visibility, attributes.last_modified) == (None, None)


def test_there_is_no_extra_metadata_unless_the_backend_gave_some() -> None:
    assert DirectoryAttributes("some/dir").extra_metadata == {}


def test_two_directories_do_not_share_their_extra_metadata() -> None:
    first = DirectoryAttributes("a")
    second = DirectoryAttributes("b")

    assert first.extra_metadata is not second.extra_metadata


def test_nothing_can_be_changed_after_the_fact() -> None:
    attributes = DirectoryAttributes("some/dir")

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(attributes, "path", "other")


def test_with_path_moves_the_description_to_another_path() -> None:
    assert DirectoryAttributes("inner/dir").with_path("outer/dir").path == "outer/dir"


def test_with_path_keeps_everything_the_backend_said() -> None:
    attributes = DirectoryAttributes(
        "inner/dir",
        visibility=Visibility.PUBLIC,
        last_modified=1_700_000_000,
        extra_metadata={"owner": "root"},
    )

    moved = attributes.with_path("outer/dir")

    assert (moved.visibility, moved.last_modified, moved.extra_metadata) == (
        Visibility.PUBLIC,
        1_700_000_000,
        {"owner": "root"},
    )


def test_with_path_strips_the_new_path_too() -> None:
    assert DirectoryAttributes("a").with_path("/b/").path == "b"


def test_with_path_leaves_the_description_it_was_called_on_alone() -> None:
    attributes = DirectoryAttributes("a")

    _ = attributes.with_path("b")

    assert attributes.path == "a"


def test_to_dict_carries_every_field_under_its_name() -> None:
    attributes = DirectoryAttributes(
        "some/dir",
        visibility=Visibility.PRIVATE,
        last_modified=1_700_000_000,
        extra_metadata={"owner": "root"},
    )

    assert attributes.to_dict() == {
        "type": "dir",
        "path": "some/dir",
        "visibility": Visibility.PRIVATE,
        "last_modified": 1_700_000_000,
        "extra_metadata": {"owner": "root"},
    }


def test_to_dict_asks_nothing_a_directory_cannot_answer() -> None:
    keys = set(DirectoryAttributes("some/dir").to_dict())

    assert keys == {"type", "path", "visibility", "last_modified", "extra_metadata"}
