"""A client application signing its users in with the fixture provider.

It shares nothing with the provider but the protocol: its own kernel, its own
security configuration, and the repository's OpenID Connect login on its one
firewall.
"""

from __future__ import annotations
