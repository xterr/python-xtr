from __future__ import annotations

import pytest

from xtr_storage.identical_path_policy import IdenticalPathPolicy


def test_every_policy_is_its_own_string() -> None:
    assert (
        IdenticalPathPolicy.TRY,
        IdenticalPathPolicy.FAIL,
        IdenticalPathPolicy.IGNORE,
    ) == ("try", "fail", "ignore")


def test_a_policy_reads_back_from_its_string() -> None:
    assert IdenticalPathPolicy("fail") is IdenticalPathPolicy.FAIL


def test_a_word_no_policy_carries_is_refused() -> None:
    with pytest.raises(ValueError, match="overwrite"):
        _ = IdenticalPathPolicy("overwrite")


def test_the_policies_are_the_only_three() -> None:
    assert list(IdenticalPathPolicy) == [
        IdenticalPathPolicy.TRY,
        IdenticalPathPolicy.FAIL,
        IdenticalPathPolicy.IGNORE,
    ]
