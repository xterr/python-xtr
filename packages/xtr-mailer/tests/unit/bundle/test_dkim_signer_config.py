from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_mailer.bundle import DkimSignerConfig
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_the_options_left_unset_take_the_signer_defaults() -> None:
    options = DkimSignerConfig("key", "example.com", "default").default_options()

    assert (
        options.get_header_canon(),
        options.get_body_canon(),
        options.get_headers_to_ignore(),
        options.get_body_show_length(),
    ) == (None, None, None, None)


def test_the_options_set_reach_the_signer() -> None:
    options = DkimSignerConfig(
        "key",
        "example.com",
        "default",
        header_canon="simple",
        body_canon="relaxed",
        headers_to_ignore=["x-mailer"],
        body_show_length=True,
    ).default_options()

    assert (
        options.get_header_canon(),
        options.get_body_canon(),
        options.get_headers_to_ignore(),
        options.get_body_show_length(),
    ) == ("simple", "relaxed", ("x-mailer",), True)


@pytest.mark.parametrize(
    ("option", "build"),
    [
        ("header_canon", lambda: DkimSignerConfig("k", "example.com", "s", header_canon="strict")),
        ("body_canon", lambda: DkimSignerConfig("k", "example.com", "s", body_canon="strict")),
    ],
)
def test_a_canonicalization_other_than_simple_or_relaxed_is_refused(
    option: str, build: Callable[[], DkimSignerConfig]
) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = build()

    assert str(caught.value) == (
        f'The DKIM "{option}" option must be "simple" or "relaxed" (got "strict").'
    )


@pytest.mark.parametrize(
    ("option", "build"),
    [
        ("key", lambda: DkimSignerConfig("", "example.com", "s")),
        ("domain", lambda: DkimSignerConfig("k", "", "s")),
        ("select", lambda: DkimSignerConfig("k", "example.com", "")),
    ],
)
def test_an_empty_required_option_is_refused(
    option: str, build: Callable[[], DkimSignerConfig]
) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = build()

    assert str(caught.value) == f'The DKIM "{option}" option cannot be empty.'


def test_its_repr_never_shows_the_key_or_the_passphrase() -> None:
    config = DkimSignerConfig("-----BEGIN KEY-----", "example.com", "default", passphrase="s3cr3t")

    assert "BEGIN" not in repr(config)
    assert "s3cr3t" not in repr(config)
