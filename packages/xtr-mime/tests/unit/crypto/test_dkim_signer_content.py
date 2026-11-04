"""A message signed with DKIM sends its body as it was signed, whatever that body holds.

Each body carries something the engine's reader would not read back to the same bytes (see
:mod:`tests.support.signed_content`); it is signed with both canonicalizations, then rendered
twice both ways.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.dkim_extra import require_dkim_extra
from tests.support.signed_content import SIGNED_CONTENTS

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.dkim_keys import dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import signer, wire  # noqa: E402 -- see above.
from xtr_mime.crypto import DkimOptions  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mime import Email, Message

_CONTENTS = pytest.mark.parametrize("build", SIGNED_CONTENTS.values(), ids=SIGNED_CONTENTS.keys())
_CANONS = pytest.mark.parametrize("canon", ["simple", "relaxed"])


def _signed(build: Callable[[], Email], canon: str) -> Message:
    options = DkimOptions().header_canon(canon).body_canon(canon)
    return signer(options).sign(build())


def _renderings(signed: Message) -> list[bytes]:
    return [
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
    ]


@_CANONS
@_CONTENTS
def test_a_signed_message_renders_the_same_bytes_every_time(
    build: Callable[[], Email], canon: str
) -> None:
    signed = _signed(build, canon)

    assert len(set(_renderings(signed))) == 1


@_CANONS
@_CONTENTS
def test_every_rendering_of_a_signed_message_verifies(
    build: Callable[[], Email], canon: str
) -> None:
    signed = _signed(build, canon)

    assert all(dkim_key().verifies(sent) for sent in _renderings(signed))
