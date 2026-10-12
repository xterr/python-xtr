"""The manager for what a deployment decided not to store at all.

One module, because there is one such decision: an access token is a signed
document a resource server reads on its own, so writing it down is optional.
Everything else this server issues has to be looked up again.
"""

from __future__ import annotations

from .access_token_manager import AccessTokenManager

__all__ = ["AccessTokenManager"]
