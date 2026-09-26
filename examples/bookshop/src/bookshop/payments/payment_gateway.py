"""A service that exists only in prod, a decorator that follows it, and one removed without it.

- ``payment_gateway`` is ``@when("prod")``: outside prod there is no
  ``PaymentGatewayInterface`` at all.
- ``RetryingPaymentGateway`` decorates it with ``on_invalid=OnInvalid.IGNORE``: where the
  gateway is missing, the decorator is dropped instead of failing the build.
- ``RefundService`` is ``@remove_if_missing(service=PaymentGatewayInterface)``: dropped where
  the gateway is missing, kept where it exists.

So ``bookshop di:show`` answers ``has(PaymentGatewayInterface)`` / ``has(RefundService)``
with ``False`` in dev and ``True`` in prod — without a single ``if`` in the code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Protocol, final, runtime_checkable

from typing_extensions import override
from xtr_dependency_injection import (
    Autowire,
    AutowireDecorated,
    OnInvalid,
    as_decorator,
    as_service,
    remove_if_missing,
    when,
)

__all__ = [
    "HttpPaymentGateway",
    "PaymentGatewayInterface",
    "RefundService",
    "RetryingPaymentGateway",
    "payment_gateway",
]


@runtime_checkable
class PaymentGatewayInterface(Protocol):
    """Charges a customer."""

    def charge(self, email: str, amount: Decimal, /) -> str:
        """Charge ``amount`` to ``email``; return the payment reference."""
        ...


@final
class HttpPaymentGateway(PaymentGatewayInterface):
    """Stands in for a payment provider's client."""

    def __init__(self, api_key: str) -> None:
        """Authenticate with ``api_key``."""
        self._key_suffix = api_key[-4:]

    @override
    def charge(self, email: str, amount: Decimal, /) -> str:
        return f"pay_{email.split('@', maxsplit=1)[0]}_{amount}_{self._key_suffix}"


@when("prod")
@as_service
def payment_gateway(
    api_key: Annotated[str, Autowire(env="SHOP_PAYMENT_API_KEY")],
) -> PaymentGatewayInterface:
    """The prod gateway; its API key is read when the gateway is first built."""
    return HttpPaymentGateway(api_key)


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


@final
@remove_if_missing(service=PaymentGatewayInterface)
@as_service
class RefundService:
    """Refunds need a gateway: this service exists only where one does."""

    def __init__(self, gateway: PaymentGatewayInterface) -> None:
        """Refund through ``gateway``."""
        self._gateway = gateway

    def refund(self, email: str, amount: Decimal) -> str:
        """Refund ``amount`` to ``email`` as a negative charge."""
        return self._gateway.charge(email, -amount)
