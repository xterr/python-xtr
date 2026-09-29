"""What a listing yields: a file or a directory."""

from __future__ import annotations

from typing import TypeAlias

from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.file_attributes import FileAttributes

__all__ = ["StorageAttributes"]

StorageAttributes: TypeAlias = FileAttributes | DirectoryAttributes
"""One entry of a listing.

A closed union rather than a base class with optional fields: the two sides
answer different questions — only a file has a size — and code that must handle
both is made to say which it is holding, through ``is_file`` or a match.
"""
