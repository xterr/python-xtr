"""Which row of the messages table an envelope was received from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import NonSendableStampInterface

__all__ = ["OrmReceivedStamp"]


@final
@dataclass(frozen=True, slots=True)
class OrmReceivedStamp(NonSendableStampInterface):
    """The row an envelope came from, which settling it deletes.

    Never sent on: it names a row of this table, which means nothing to a
    transport the envelope is dispatched to next.
    """

    id: str
