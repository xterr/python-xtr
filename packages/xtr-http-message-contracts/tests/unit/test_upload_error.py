from __future__ import annotations

import pytest

from xtr_http_message_contracts import UploadError


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (UploadError.OK, 0),
        (UploadError.INI_SIZE, 1),
        (UploadError.FORM_SIZE, 2),
        (UploadError.PARTIAL, 3),
        (UploadError.NO_FILE, 4),
        (UploadError.NO_TMP_DIR, 6),
        (UploadError.CANT_WRITE, 7),
        (UploadError.EXTENSION, 8),
    ],
)
def test_a_member_carries_the_number_the_wire_uses(member: UploadError, value: int) -> None:
    assert member == value


def test_the_members_are_the_eight_outcomes_and_no_more() -> None:
    assert [member.name for member in UploadError] == [
        "OK",
        "INI_SIZE",
        "FORM_SIZE",
        "PARTIAL",
        "NO_FILE",
        "NO_TMP_DIR",
        "CANT_WRITE",
        "EXTENSION",
    ]


def test_no_member_carries_five() -> None:
    with pytest.raises(ValueError, match="5 is not a valid UploadError"):
        _ = UploadError(5)
