"""The bundles the served fixture activates: the security bundle and its peers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from xtr_security.bundle import SecurityBundle

if TYPE_CHECKING:
    from xtr_dependency_injection.bundle.bundle import AnyBundle

BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {SecurityBundle: {"all": True}}
