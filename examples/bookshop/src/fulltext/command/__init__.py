"""The library's console commands — scanned late, only when a console bundle is active."""

from __future__ import annotations

from .search_commands import SearchStatsCommand, search_query

__all__ = ["SearchStatsCommand", "search_query"]
