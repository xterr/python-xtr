"""The ai bundle alone: the orm is installed, but the application does not list it."""

from __future__ import annotations

from xtr_ai.bundle import AiBundle

BUNDLES = {AiBundle: {"all": True}}
