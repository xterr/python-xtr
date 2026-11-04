from __future__ import annotations

import pytest

from xtr_mailer.bundle import TransportConfig
from xtr_mailer.exception import InvalidArgumentError


def test_a_transport_is_capped_by_no_rate_limiter_by_default() -> None:
    assert TransportConfig("null://null").rate_limiter is None


def test_an_empty_dsn_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TransportConfig("")

    assert str(caught.value) == "A transport's DSN cannot be empty."


def test_an_empty_rate_limiter_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TransportConfig("null://null", rate_limiter="")

    assert str(caught.value) == "A transport's rate limiter name cannot be empty."


def test_its_repr_never_shows_the_dsn() -> None:
    assert "s3cr3t" not in repr(TransportConfig("smtp://user:s3cr3t@localhost"))
