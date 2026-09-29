from __future__ import annotations

from typing import get_args

from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.storage_attributes import StorageAttributes


def test_a_listing_entry_is_a_file_or_a_directory() -> None:
    assert get_args(StorageAttributes) == (FileAttributes, DirectoryAttributes)


def test_both_kinds_of_entry_answer_where_they_are() -> None:
    entries: list[StorageAttributes] = [FileAttributes("a.txt"), DirectoryAttributes("some/dir")]

    assert [entry.path for entry in entries] == ["a.txt", "some/dir"]


def test_both_kinds_of_entry_say_which_they_are() -> None:
    entries: list[StorageAttributes] = [FileAttributes("a.txt"), DirectoryAttributes("some/dir")]

    assert [entry.is_file for entry in entries] == [True, False]
