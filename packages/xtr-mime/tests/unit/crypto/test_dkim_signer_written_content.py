"""A message signed with DKIM verifies with an 8bit body at its top or an attached message.

Each message (see :mod:`tests.support.written_content`) is signed with the ``simple``
canonicalizations, which a changed byte breaks, then rendered both ways.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.dkim_extra import require_dkim_extra
from tests.support.written_content import WRITTEN_CONTENTS, assert_written

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.dkim_keys import dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import signer, wire  # noqa: E402 -- see above.
from xtr_mime.crypto import DkimOptions  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from tests.support.written_content import WrittenContent

_CONTENTS = pytest.mark.parametrize(
    "content", WRITTEN_CONTENTS.values(), ids=WRITTEN_CONTENTS.keys()
)


@_CONTENTS
def test_every_rendering_of_the_signed_message_verifies(content: WrittenContent) -> None:
    options = DkimOptions().header_canon("simple").body_canon("simple")
    signed = signer(options).sign(content.build())

    sent = [wire(signed), signed.to_string().encode("utf-8", "surrogateescape")]

    assert all(dkim_key().verifies(rendering) for rendering in sent)
    assert_written(content, sent[0])
