from __future__ import annotations

import pytest

from xtr_mailer.data_collector._masking import MASK, masked_header


@pytest.mark.parametrize(
    "name", ["Authorization", "proxy-authorization", "Cookie", "Set-Cookie", "X-API-KEY"]
)
def test_a_credential_header_is_masked(name: str) -> None:
    assert masked_header(name, "Bearer abc") == MASK


@pytest.mark.parametrize(
    "name", ["X-Auth-Token", "X-Password", "X-Client-Secret", "X-Passwd", "X-Api_Key", "Apikey"]
)
def test_a_header_named_like_a_credential_is_masked(name: str) -> None:
    assert masked_header(name, "s3cr3t") == MASK


def test_any_other_header_is_kept() -> None:
    assert masked_header("X-Campaign", "spring") == "spring"


def test_the_mask_is_six_stars() -> None:
    assert MASK == "******"
