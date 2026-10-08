from __future__ import annotations

from pathlib import Path

from xtr_cli.exception import DirectoryNotEmptyError


def test_it_lists_at_most_five_entries_in_the_way() -> None:
    error = DirectoryNotEmptyError(Path("shop"), tuple("abcdefg"))

    assert str(error) == "shop is not empty (a, b, c, d, e, …): choose a new directory"
    assert error.found == tuple("abcdefg")
