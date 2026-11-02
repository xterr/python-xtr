"""The application's root bundles: the orm messenger bundle brings the orm and the bus."""

from __future__ import annotations

from xtr_orm_messenger.bundle import OrmMessengerBundle

BUNDLES = {OrmMessengerBundle: {"all": True}}
