"""A decorator standing in for a service nobody defines: ``OnInvalid.NULL``.

Nothing registers a ``FraudCheckInterface`` — a provider's scoring service would, in a
larger shop. ``LimitFraudCheck`` decorates it with ``on_invalid=OnInvalid.NULL``: the
decorator is kept under ``FraudCheckInterface`` and receives ``None`` for what it wraps,
which its annotation must allow (``FraudCheckInterface | None``). Once a real scorer is
registered, the same decorator wraps it, unchanged.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Protocol, final, runtime_checkable

from typing_extensions import override
from xtr_dependency_injection import Autowire, AutowireDecorated, OnInvalid, as_decorator

__all__ = ["FraudCheckInterface", "LimitFraudCheck"]


@runtime_checkable
class FraudCheckInterface(Protocol):
    """Scores how suspicious an order is, from 0 (fine) to 1 (refuse)."""

    def score(self, email: str, amount: Decimal, /) -> float:
        """Score an order of ``amount`` by ``email``."""
        ...


@final
@as_decorator(FraudCheckInterface, on_invalid=OnInvalid.NULL)
class LimitFraudCheck(FraudCheckInterface):
    """Refuses orders above a limit, then defers to the wrapped scorer when there is one."""

    def __init__(
        self,
        inner: Annotated[FraudCheckInterface | None, AutowireDecorated()],
        limit: Annotated[float, Autowire(env="float:SHOP_FRAUD_LIMIT")],
    ) -> None:
        """Refuse above ``limit``; ask ``inner`` otherwise, when it exists."""
        self._inner = inner
        self._limit = Decimal(str(limit))

    @property
    def wraps_a_scorer(self) -> bool:
        """Whether a real scorer is registered underneath."""
        return self._inner is not None

    @override
    def score(self, email: str, amount: Decimal, /) -> float:
        if amount > self._limit:
            return 1.0
        return 0.0 if self._inner is None else self._inner.score(email, amount)
