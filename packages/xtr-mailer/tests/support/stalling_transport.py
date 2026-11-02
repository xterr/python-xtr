"""A transport whose first send never finishes, so a test can cancel it mid-send."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
from typing_extensions import override

from tests.support.fake_transport import FakeTransport

if TYPE_CHECKING:
    from xtr_mailer import SentMessage

__all__ = ["StallingTransport"]


class StallingTransport(FakeTransport):
    """Hangs on its first send until cancelled; sends every later one as the fake does."""

    stalled: bool = False

    @override
    async def _do_send(self, message: SentMessage) -> None:
        if not self.stalled:
            self.stalled = True
            await anyio.sleep_forever()
        await super()._do_send(message)
