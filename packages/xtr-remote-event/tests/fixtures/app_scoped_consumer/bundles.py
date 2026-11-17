"""The application's root bundles: only RemoteEventBundle, which brings messenger."""

from __future__ import annotations

from xtr_remote_event.bundle import RemoteEventBundle

BUNDLES = {RemoteEventBundle: {"all": True}}
