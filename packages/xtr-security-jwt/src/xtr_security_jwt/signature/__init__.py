"""The value objects a JWS provider hands back around a token."""

from __future__ import annotations

from .created_jws import CreatedJws
from .loaded_jws import LoadedJws

__all__ = ["CreatedJws", "LoadedJws"]
