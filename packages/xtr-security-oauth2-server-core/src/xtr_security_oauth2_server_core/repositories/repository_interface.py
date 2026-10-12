"""What marks a contract as one of this server's storage contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["RepositoryInterface"]


@runtime_checkable
class RepositoryInterface(Protocol):
    """The marker every storage contract here is grouped under.

    It asks for nothing. What it buys is a single name for "something this
    server stores its state through", so a reader of the wiring, a container
    registration or a piece of documentation can say *repository* and mean
    exactly these contracts — and so the contracts themselves read as a family
    rather than as seven unrelated protocols.

    Because it declares no member, every object satisfies it at runtime. Ask a
    particular contract — the client one, the access-token one — when the
    question is whether something can actually do the job.
    """
