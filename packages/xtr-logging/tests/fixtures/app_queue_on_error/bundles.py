"""Bundles for a fixture app whose queue handler reports failures to a named service."""

from __future__ import annotations

from xtr_logging.bundle import LoggingBundle

BUNDLES = {LoggingBundle: {"all": True}}
