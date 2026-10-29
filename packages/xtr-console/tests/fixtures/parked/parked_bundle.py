"""A bundle installed, as far as a test says, that an application lists by name."""

from __future__ import annotations

from xtr_dependency_injection import Bundle, as_bundle

__all__ = ["ParkedBundle"]


@as_bundle("parked")
class ParkedBundle(Bundle):
    """Defined here, and named by its package."""
