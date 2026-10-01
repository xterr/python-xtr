"""The bundles the fixture application activates."""

from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003 -- the kernel reads the BUNDLES annotation
from typing import TYPE_CHECKING

from xtr_security_jwt.bundle import JwtBundle

if TYPE_CHECKING:
    from xtr_dependency_injection.bundle.bundle import AnyBundle

__all__ = ["BUNDLES"]

BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {JwtBundle: {"all": True}}
