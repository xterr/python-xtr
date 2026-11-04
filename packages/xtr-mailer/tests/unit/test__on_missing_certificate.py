from __future__ import annotations

import pytest

from xtr_mailer._on_missing_certificate import MODES, checked_mode
from xtr_mailer.exception import InvalidArgumentError


@pytest.mark.parametrize("mode", sorted(MODES))
def test_a_known_mode_is_returned(mode: str) -> None:
    assert checked_mode(mode) == mode


def test_an_unknown_mode_is_refused_quoting_it() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = checked_mode("Skip")

    assert str(caught.value) == (
        'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" (got "Skip").'
    )


def test_a_mode_that_is_not_text_is_refused_naming_its_type() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = checked_mode(None)

    assert str(caught.value) == (
        'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" '
        '(got a value of type "NoneType").'
    )
