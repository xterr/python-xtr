"""A package re-exporting its bundle, as every installed package does.

Re-exported, the bundle has two spellings: ``tests.fixtures.parked:ParkedBundle``,
the one an application lists it by, and the module that defines it.
"""

from __future__ import annotations

from .parked_bundle import ParkedBundle

__all__ = ["ParkedBundle"]
