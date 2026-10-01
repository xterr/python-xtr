"""A voter that can say up front what it votes on."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .voter_interface import VoterInterface

__all__ = ["CacheableVoterInterface"]


@runtime_checkable
class CacheableVoterInterface(VoterInterface, Protocol):
    """A voter that declares which attributes and subject types it votes on.

    A decision manager asks many voters about the same kinds of attribute and
    subject over and over. A voter that can answer, cheaply and without state,
    whether it has anything to say about an attribute or a subject type lets
    the manager remember that answer and skip the voter when it does not —
    turning a per-request scan into a lookup. It is a
    :class:`~xtr_security_core.authorization.voter.voter_interface.VoterInterface`
    that adds this declaration.
    """

    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether this voter ever votes on ``attribute``."""
        ...

    def supports_type(self, subject_type: str) -> bool:
        """Tell whether this voter ever votes on a subject of ``subject_type``."""
        ...
