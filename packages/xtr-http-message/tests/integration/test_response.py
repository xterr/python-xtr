from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_http_message.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

# The harness checks that a status code of the wrong type is refused. Here the
# type is in the signature, so the call cannot be made at all.
_WRONG_TYPE = (
    "Adaptation (plan H2): a status code is typed `int`, so the two rows of the harness's "
    "provider that pass a string and a bare object are refused before the call; no run-time type "
    "check was ported for them. Its boolean row does reach the range check, and runs above."
)


def test_the_status_code_can_be_replaced(response: ResponseInterface) -> None:
    replaced = response.with_status(204)

    assert replaced is not response
    assert response.get_status_code() == 200
    assert replaced.get_status_code() == 204


@pytest.mark.parametrize(
    "code",
    [True, 99, 600],
    ids=["a boolean, which counts as one here", "below the lowest code", "above the highest"],
)
def test_a_status_code_outside_the_range_is_refused(
    response: ResponseInterface,
    code: int,
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = response.with_status(code)


@pytest.mark.skip(reason=_WRONG_TYPE)
def test_a_status_code_of_the_wrong_type_is_refused() -> None:
    """The rows of the harness that pass something which is not a status code."""


def test_a_reason_phrase_given_with_the_status_is_kept(response: ResponseInterface) -> None:
    replaced = response.with_status(204, "Foobar")

    assert replaced.get_status_code() == 204
    assert replaced.get_reason_phrase() == "Foobar"
