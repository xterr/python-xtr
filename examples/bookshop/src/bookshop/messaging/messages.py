"""The messages the shop dispatches, in every shape ``@as_message`` takes.

==================  ==========================  ==================  ========================
Message             Shape                       Wire name           Where it goes
==================  ==========================  ==================  ========================
``PlaceOrder``      dataclass                   pinned, versioned   routing table: ``sync``
``SendReceipt``     dataclass                   pinned, versioned   routing table: fan-out
``ReindexCatalog``  pydantic model              pinned, versioned   its own ``transport=``
``StockAlert``      dataclass                   ``module:QualName`` its own ``transport=[...]``
``AuditEvent``      dataclass, bare decorator   ``module:QualName`` nowhere: handled locally
==================  ==========================  ==================  ========================

Routing resolves most specific first: a ``TransportNamesStamp`` on the envelope, then the
routing table (walking the message's bases), then ``"*"``, then what the message declared.
A message's annotations are read at runtime, so their types are imported for real.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from xtr_messenger import as_message

__all__ = ["AuditEvent", "PlaceOrder", "ReindexCatalog", "SendReceipt", "StockAlert"]


@as_message(name="bookshop.order.place.v1")
@dataclass(frozen=True, slots=True)
class PlaceOrder:
    """Record an order. Routed to ``sync``: handled during the dispatch, in this process."""

    order_id: UUID
    number: str
    isbn: str
    quantity: int
    email: str
    total: Decimal


@as_message(name="bookshop.order.receipt.v1")
@dataclass(frozen=True, slots=True)
class SendReceipt:
    """Mail the customer a receipt. Fanned out to ``jobs`` and ``audit``."""

    order_id: UUID
    email: str
    total: Decimal


@as_message(name="bookshop.catalog.reindex.v1", transport="jobs")
class ReindexCatalog(BaseModel):
    """Rebuild the search index — a pydantic model, validated by its own rules.

    Not in the routing table: it goes to the transport it declares, ``jobs``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[str, Field(min_length=3)]
    isbns: tuple[str, ...] = ()


@as_message(transport=["outbox"])
@dataclass(frozen=True, slots=True)
class StockAlert:
    """Tell purchasing a title sells fast. Declares a list of transports — one here."""

    isbn: str
    ordered: int


@as_message
@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Something worth an audit trail. Routed nowhere and declaring nothing.

    With ``handle_unrouted=True`` in the dev configuration it is handled in this process;
    with ``require_sender=True`` in prod the routing table's ``"*"`` sends it on.
    """

    subject: str
    detail: str
