"""Startup checks: tagged items ordered with ``before``/``after``, run by a boot hook."""

from __future__ import annotations

from .startup_check import STARTUP_CHECK_TAG, StartupCheck

__all__ = ["STARTUP_CHECK_TAG", "StartupCheck"]
