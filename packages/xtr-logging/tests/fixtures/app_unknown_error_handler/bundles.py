"""Bundles for a fixture app whose queue handler names an unsupplied error handler."""

from __future__ import annotations

from xtr_logging.bundle import LoggingBundle

BUNDLES = {LoggingBundle: {"all": True}}
