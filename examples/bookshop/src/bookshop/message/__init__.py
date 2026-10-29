"""The messages the shop dispatches, in every shape ``@as_message`` takes.

==================  ==========================  ==================  ========================
Message             Shape                       Wire name           Where it goes
==================  ==========================  ==================  ========================
``PlaceOrder``      dataclass                   pinned, versioned   routing table: ``sync``
``SendReceipt``     dataclass                   pinned, versioned   routing table: fan-out
``ReindexCatalog``  pydantic model              pinned, versioned   its own ``transport=``
``StockAlert``      dataclass                   pinned, as before   its own ``transport=[...]``
``AuditEvent``      dataclass                   pinned, as before   nowhere: handled locally
``RestockCheck``    dataclass, ``__str__``      pinned, versioned   the schedule's worker
==================  ==========================  ==================  ========================

``StockAlert`` and ``AuditEvent`` keep the ``module:QualName`` they travelled under before
they moved here: without ``name=`` a message travels as ``module:QualName``, which changes
when the class moves — so a message that outlives a deploy pins its name.

Routing resolves most specific first: a ``TransportNamesStamp`` on the envelope, then the
routing table (walking the message's bases), then ``"*"``, then what the message declared.
A message's annotations are read at runtime, so their types are imported for real.
"""

from __future__ import annotations

__all__: list[str] = []
