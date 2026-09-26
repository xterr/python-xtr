"""The application's root bundles: only ClockBundle, activated in every env."""

from __future__ import annotations

from xtr_clock.bundle import ClockBundle

BUNDLES = {ClockBundle: {"all": True}}
