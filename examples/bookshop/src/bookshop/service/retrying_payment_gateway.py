"""A decorator that follows the gateway: dropped where there is none (``OnInvalid.IGNORE``)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import AutowireDecorated, OnInvalid, as_decorator

from bookshop.service.payment_gateway_interface import PaymentGatewayInterface

__all__ = ["RetryingPaymentGateway"]


@final
@as_decorator(PaymentGatewayInterface, priority=5, on_invalid=OnInvalid.IGNORE)
class RetryingPaymentGateway(PaymentGatewayInterface):
    """Retries a failed charge once. Dropped where there is no gateway to decorate."""

    def __init__(self, inner: Annotated[PaymentGatewayInterface, AutowireDecorated()]) -> None:
        """Wrap ``inner``."""
        self._inner = inner

    @override
    def charge(self, email: str, amount: Decimal, /) -> str:
        try:
            return self._inner.charge(email, amount)
        except ConnectionError:
            return self._inner.charge(email, amount)
