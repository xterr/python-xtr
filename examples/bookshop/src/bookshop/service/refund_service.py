"""A service removed where the gateway is missing: ``@remove_if_missing(service=...)``."""

from __future__ import annotations

from decimal import Decimal
from typing import final

from xtr_dependency_injection import as_service, remove_if_missing

from bookshop.service.payment_gateway_interface import PaymentGatewayInterface

__all__ = ["RefundService"]


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
