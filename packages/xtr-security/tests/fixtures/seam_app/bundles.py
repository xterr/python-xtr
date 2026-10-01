"""The bundles the seam fixture activates: the fake bundle, which requires security."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from tests.fixtures.seam_app.bundle import FakeOAuth2Bundle

if TYPE_CHECKING:
    from xtr_dependency_injection.bundle.bundle import AnyBundle

BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {FakeOAuth2Bundle: {"all": True}}
