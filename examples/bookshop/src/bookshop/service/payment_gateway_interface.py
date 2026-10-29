"""What charges a customer — a service that exists only in prod.

- ``payment_gateway`` (in ``http_payment_gateway``) is ``@when("prod")``: outside prod there
  is no ``PaymentGatewayInterface`` at all.
- ``RetryingPaymentGateway`` decorates it with ``on_invalid=OnInvalid.IGNORE``: where the
  gateway is missing, the decorator is dropped instead of failing the build.
- ``RefundService`` is ``@remove_if_missing(service=PaymentGatewayInterface)``: dropped where
  the gateway is missing, kept where it exists.

So ``bookshop di:show`` answers ``has(PaymentGatewayInterface)`` / ``has(RefundService)``
with ``False`` in dev and ``True`` in prod — without a single ``if`` in the code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

__all__ = ["PaymentGatewayInterface"]


@runtime_checkable
class PaymentGatewayInterface(Protocol):
    """Charges a customer."""

    def charge(self, email: str, amount: Decimal, /) -> str:
        """Charge ``amount`` to ``email``; return the payment reference."""
        ...
