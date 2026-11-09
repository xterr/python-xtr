"""Where the identity layer finds the users it describes.

One contract, :class:`IdentityProviderInterface`: an application implements it
over wherever it already keeps its users — a relational database, a directory,
a remote service — and the identity layer looks them up through nothing else.
The lookup is awaitable, because it may reach that storage.
"""

from __future__ import annotations

from .identity_provider_interface import IdentityProviderInterface

__all__ = ["IdentityProviderInterface"]
