"""A message signed with S/MIME sends its signed part as it was signed, whatever that part holds.

Each body carries something the engine's reader would not read back to the same bytes (see
:mod:`tests.support.signed_content`); it is signed, then rendered twice both ways.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.signed_content import SIGNED_CONTENTS
from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.smime_certificates import authority  # noqa: E402 -- see above.
from tests.support.smime_checks import openssl_verifies, verifies, wire  # noqa: E402 -- see above.
from tests.support.smime_signing import signer  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from xtr_mime import Email, Message

_CONTENTS = pytest.mark.parametrize("build", SIGNED_CONTENTS.values(), ids=SIGNED_CONTENTS.keys())


def _renderings(signed: Message) -> list[bytes]:
    return [
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
    ]


@_CONTENTS
def test_a_signed_message_renders_the_same_bytes_every_time(
    tmp_path: Path, build: Callable[[], Email]
) -> None:
    signed = signer(tmp_path).sign(build())

    assert len(set(_renderings(signed))) == 1


@_CONTENTS
def test_every_rendering_of_a_signed_message_verifies(
    tmp_path: Path, build: Callable[[], Email]
) -> None:
    signed = signer(tmp_path).sign(build())

    assert all(verifies(sent, authority().certificate) for sent in _renderings(signed))


@_CONTENTS
def test_openssl_verifies_the_signed_message_where_it_is_installed(
    tmp_path: Path, build: Callable[[], Email]
) -> None:
    sent = wire(signer(tmp_path).sign(build()))

    verified = openssl_verifies(sent, authority().certificate, tmp_path)

    if verified is None:
        pytest.skip("no openssl binary installed")
    assert verified
