"""Passports and the badges they carry, produced by an authenticator."""

from __future__ import annotations

from .passport import Passport
from .self_validating_passport import SelfValidatingPassport

__all__ = ["Passport", "SelfValidatingPassport"]
