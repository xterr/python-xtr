"""The application's root bundles: only LoggingBundle, activated in every env."""

from __future__ import annotations

from xtr_logging.bundle import LoggingBundle

BUNDLES = {LoggingBundle: {"all": True}}
