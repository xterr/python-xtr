"""Signing messages, so a receiver can tell who sent them and that nothing changed on the way.

:class:`DkimSigner` adds a DKIM signature for a domain; it needs the ``dkim`` extra, which
importing this package does not.
"""

from __future__ import annotations

from .dkim_options import DkimOptions
from .dkim_signer import DkimSigner

__all__ = ["DkimOptions", "DkimSigner"]
