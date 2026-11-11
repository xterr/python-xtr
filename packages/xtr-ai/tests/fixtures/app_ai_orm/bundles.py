"""The ai bundle beside the orm."""

from __future__ import annotations

from xtr_orm.bundle import OrmBundle

from xtr_ai.bundle import AiBundle

BUNDLES = {AiBundle: {"all": True}, OrmBundle: {"all": True}}
