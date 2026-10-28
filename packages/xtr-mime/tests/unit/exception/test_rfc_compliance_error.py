from __future__ import annotations

from xtr_mime.exception import InvalidArgumentError, RfcComplianceError


def test_it_is_an_invalid_argument() -> None:
    assert issubclass(RfcComplianceError, InvalidArgumentError)
