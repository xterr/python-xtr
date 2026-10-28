"""An arc says how many tokens a transition moves through one place."""

from __future__ import annotations

import pytest

from xtr_workflow import Arc
from xtr_workflow.exception import InvalidArgumentError


def test_an_empty_place_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = Arc("", 1)

    assert str(raised.value) == "The place name cannot be empty."


def test_a_weight_below_one_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = Arc("not empty", 0)

    assert str(raised.value) == "The weight must be greater than 0, 0 given."


def test_a_place_named_zero_is_a_place() -> None:
    arc = Arc("0", 1)

    assert arc.place == "0"


def test_an_arc_weighs_one_unless_told_otherwise() -> None:
    assert Arc("a").weight == 1
