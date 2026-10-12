"""Building a firewall's access-token authenticator from its configuration.

The security bundle keeps a registry of authenticator factories; this package's
bundle adds :class:`OAuth2Factory` to it, which is what makes the firewall key
``oauth2`` mean something to an application.
"""

from __future__ import annotations

from .oauth2_factory import OAuth2Factory

__all__ = ["OAuth2Factory"]
