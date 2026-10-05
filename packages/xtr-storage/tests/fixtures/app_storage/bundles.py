"""The application's root bundles: only StorageBundle, in every environment."""

from __future__ import annotations

from xtr_storage.bundle import StorageBundle

BUNDLES = {StorageBundle: {"all": True}}
