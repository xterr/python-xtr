"""The wrappers that record what a firewall's authenticators did, for the tooling."""

from __future__ import annotations

from .traceable_authenticator import TraceableAuthenticator
from .unsupported_reasons import UnsupportedReasons

__all__ = ["TraceableAuthenticator", "UnsupportedReasons"]
