"""SyncOptions: the two choices a sync offers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["SyncOptions"]


@final
@dataclass(frozen=True, slots=True)
class SyncOptions:
    """How to run one sync.

    The defaults are the whole sync: every installed recipe against the lock,
    and nothing overwritten that the sync does not own.

    Attributes:
        force: Overwrite a file the application owner has edited or that was
            adopted, instead of putting the new content beside it.
        only: Re-apply one package and leave the rest of the lock alone;
            ``None`` syncs everything. Re-applying is unconditional — a
            package whose recipe has not changed is applied again anyway,
            which is what makes it a way to restore a file that went missing.
    """

    force: bool = False
    only: str | None = None
