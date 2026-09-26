"""Bundles for a fixture app whose LoggingConfig names an unsupplied handler id."""

from __future__ import annotations

from xtr_logging.bundle import LoggingBundle

BUNDLES = {LoggingBundle: {"all": True}}
