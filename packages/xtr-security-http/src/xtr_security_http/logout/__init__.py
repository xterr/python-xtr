"""Generating the paths, URLs and forms a logout is asked through."""

from __future__ import annotations

from .logout_form import LogoutForm
from .logout_url_generator import LogoutUrlGenerator

__all__ = ["LogoutForm", "LogoutUrlGenerator"]
