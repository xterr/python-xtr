from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_mailer.bundle import SmimeSignerConfig
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_signer_needs_no_passphrase_nor_extra_certificates() -> None:
    config = SmimeSignerConfig("sign.crt", "sign.key")

    assert (config.passphrase, config.extra_certificates) == ("", None)


@pytest.mark.parametrize(
    ("option", "build"),
    [
        ("certificate", lambda: SmimeSignerConfig("", "sign.key")),
        ("key", lambda: SmimeSignerConfig("sign.crt", "")),
    ],
)
def test_an_empty_required_option_is_refused(
    option: str, build: Callable[[], SmimeSignerConfig]
) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = build()

    assert str(caught.value) == f'The S/MIME signer "{option}" option cannot be empty.'


def test_its_repr_never_shows_the_passphrase() -> None:
    assert "s3cr3t" not in repr(SmimeSignerConfig("sign.crt", "sign.key", passphrase="s3cr3t"))
