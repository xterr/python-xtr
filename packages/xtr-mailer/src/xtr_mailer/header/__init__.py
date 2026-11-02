"""Provider-neutral headers: a provider transport turns each into the provider's own setting.

:class:`TagHeader` files an email under a tag, :class:`MetadataHeader` keeps a value with it,
:class:`TrackingHeader` asks for open and click tracking. A transport without such settings
sends them as the plain headers they are.
"""

from __future__ import annotations

from .metadata_header import MetadataHeader
from .tag_header import TagHeader
from .tracking_header import TrackingHeader

__all__ = ["MetadataHeader", "TagHeader", "TrackingHeader"]
