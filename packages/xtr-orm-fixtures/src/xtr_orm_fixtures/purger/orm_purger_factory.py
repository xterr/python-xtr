"""The purger factory a run uses unless told otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from .orm_purger import OrmPurger
from .purge_mode import PurgeMode
from .purger_factory_interface import PurgerFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy import MetaData

    from .purger_interface import PurgerInterface

__all__ = ["OrmPurgerFactory"]


@final
class OrmPurgerFactory(PurgerFactoryInterface):
    """Builds an :class:`OrmPurger` over the connection's table definitions.

    Every connection is emptied the same way, so the connection's name is not
    read.
    """

    __slots__ = ()

    @override
    def create_for_connection(
        self,
        connection: str,
        metadata: MetaData | Sequence[MetaData],
        *,
        excluded: Iterable[str] = (),
        purge_with_truncate: bool = False,
    ) -> PurgerInterface:
        del connection
        mode = PurgeMode.TRUNCATE if purge_with_truncate else PurgeMode.DELETE
        return OrmPurger(metadata, excluded, mode)
