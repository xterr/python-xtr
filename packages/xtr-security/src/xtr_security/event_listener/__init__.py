"""The listeners the security bundle adds to the application's dispatcher."""

from __future__ import annotations

from .vote_listener import on_vote

__all__ = ["on_vote"]
