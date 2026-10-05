from __future__ import annotations

import pytest

from xtr_storage.link_handling import LinkHandling


def test_every_choice_is_its_own_string() -> None:
    assert (LinkHandling.SKIP, LinkHandling.DISALLOW) == ("skip", "disallow")


def test_a_choice_reads_back_from_its_string() -> None:
    assert LinkHandling("disallow") is LinkHandling.DISALLOW


def test_a_word_no_choice_carries_is_refused() -> None:
    with pytest.raises(ValueError, match="follow"):
        _ = LinkHandling("follow")


def test_the_choices_are_the_only_two() -> None:
    assert list(LinkHandling) == [LinkHandling.SKIP, LinkHandling.DISALLOW]
