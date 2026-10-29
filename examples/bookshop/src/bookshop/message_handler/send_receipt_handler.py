"""A function handler of ``SendReceipt``, run by a worker; ``ReceiptCounter`` handles it too."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Autowire, Injected, Target
from xtr_messenger import Envelope, ReceivedStamp, RedeliveryStamp, as_message_handler
from xtr_rate_limiter import RateLimiterFactoryInterface

from bookshop.entity.receipt import Receipt
from bookshop.message.send_receipt import SendReceipt
from bookshop.repository.order_repository import OrderRepository
from bookshop.repository.receipt_repository import ReceiptRepository
from bookshop.service.notifier_interface import NotifierInterface
from bookshop.stamp.origin_stamp import OriginStamp

__all__ = ["send_receipt"]

_MAIL_WAIT = 30.0


@as_message_handler(SendReceipt)
async def send_receipt(  # noqa: PLR0913, PLR0917 — the message, its envelope, and what the container provides.
    message: SendReceipt,
    envelope: Envelope,
    notifier: Injected[NotifierInterface],
    orders: Injected[OrderRepository],
    receipts: Injected[ReceiptRepository],
    currency: Annotated[str, Autowire(param="shop.currency")],
    mail_rate: Annotated[RateLimiterFactoryInterface, Target("outbound_mail")],
) -> None:
    """Mail the receipt and record it — a function handler, run by a worker.

    The order was committed by the unit of work that handled ``PlaceOrder`` before this
    message was sent; this message is a unit of its own, so the receipt row is committed — or
    rolled back — with it. A redelivered message whose receipt was recorded already records
    none again.

    The mail provider takes ten a minute (``outbound_mail``): the receipt reserves its slot and
    waits for it, up to half a minute — a limit outside any web route.

    Raises:
        ValueError: For an address under the reserved ``.invalid`` domain — which is how
            ``demo:errors`` shows a worker rejecting a message and carrying on.
        MaxWaitDurationExceededError: If the provider would make the receipt wait longer;
            the worker retries the message later, and nothing was reserved.
    """
    if message.email.endswith(".invalid"):
        raise ValueError(f"cannot mail {message.email}")
    order = await orders.get_one_or_none(id=message.order_id)
    attempt = envelope.last(RedeliveryStamp)
    origin = envelope.last(OriginStamp)  # declared with @as_stamp: it survives the transport
    received = envelope.last(ReceivedStamp)
    number = origin.order_number if origin else (order.number if order else str(message.order_id))
    retry = f" (retry {attempt.retry_count})" if attempt else ""
    transport = received.transport_name if received else "-"
    if not await receipts.exists(order_id=message.order_id, transport=transport):
        _ = await receipts.add(
            Receipt(order_id=message.order_id, email=message.email, transport=transport)
        )
    reservation = await mail_rate.create("provider").reserve(max_time=_MAIL_WAIT)
    await reservation.wait()
    _ = notifier.notify(message.email, f"receipt for {number}: {message.total} {currency}{retry}")
