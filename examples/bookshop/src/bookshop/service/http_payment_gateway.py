"""The prod payment gateway, and the ``@when("prod")`` factory that registers it."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, as_service, when

from bookshop.service.payment_gateway_interface import PaymentGatewayInterface

__all__ = ["HttpPaymentGateway", "payment_gateway"]


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
