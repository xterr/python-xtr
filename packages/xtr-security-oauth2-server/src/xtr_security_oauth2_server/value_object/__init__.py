"""The three small values a client's registration is written in.

A grant, a redirect URI and a scope are each nothing but a string — and that
is exactly why they are types here. A client holds lists of all three, a
listing is narrowed by any of them, and a stored row is read back into them;
passing bare strings around would let a scope be registered where a grant
belongs and nothing would notice until a token came out wrong.

Each one is immutable, compares and hashes by what it says, and reads as that
string, so a set of them serialises and a mapping can be keyed by one. A
redirect URI is checked when it is made, which means a stored one is always a
URI.
"""

from __future__ import annotations

from .grant import Grant
from .redirect_uri import RedirectUri
from .scope import Scope

__all__ = ["Grant", "RedirectUri", "Scope"]
