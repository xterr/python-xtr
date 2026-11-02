"""S/MIME signs and encrypts a message with an 8bit body at its top or an attached message.

Each message (see :mod:`tests.support.written_content`) is signed and verified, and encrypted
and decrypted back to what it sent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.smime_extra import require_smime_extra
from tests.support.written_content import WRITTEN_CONTENTS, assert_written

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.smime_certificates import authority, recipient  # noqa: E402 -- see above.
from tests.support.smime_checks import decrypt, verifies, wire  # noqa: E402 -- see above.
from tests.support.smime_signing import encrypter, signer  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.written_content import WrittenContent

_CONTENTS = pytest.mark.parametrize(
    "content", WRITTEN_CONTENTS.values(), ids=WRITTEN_CONTENTS.keys()
)


@_CONTENTS
def test_every_rendering_of_the_signed_message_verifies(
    tmp_path: Path, content: WrittenContent
) -> None:
    signed = signer(tmp_path).sign(content.build())

    sent = [wire(signed), signed.to_string().encode("utf-8", "surrogateescape")]

    assert all(verifies(rendering, authority().certificate) for rendering in sent)


@_CONTENTS
def test_the_encrypted_message_decrypts_to_the_message_as_written(
    tmp_path: Path, content: WrittenContent
) -> None:
    encrypted = encrypter(tmp_path).encrypt(content.build())

    decrypted = decrypt(wire(encrypted), recipient())

    assert_written(content, decrypted)
