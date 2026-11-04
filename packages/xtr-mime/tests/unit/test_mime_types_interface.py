"""A table of MIME types is a guesser too, and a guesser alone is no table."""

from __future__ import annotations

import inspect

from xtr_mime import MagicMimeTypeGuesser, MimeTypeGuesserInterface, MimeTypesInterface


def test_a_table_of_types_is_also_a_guesser() -> None:
    assert MimeTypeGuesserInterface in inspect.getmro(MimeTypesInterface)


def test_a_guesser_alone_is_not_a_table_of_types() -> None:
    candidate: object = MagicMimeTypeGuesser()

    assert not isinstance(candidate, MimeTypesInterface)
