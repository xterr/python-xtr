"""Helpers for testing code built on xtr-ai.

:func:`override_agent_model` swaps a configured agent's model for one a test
scripts.
"""

from __future__ import annotations

from .override_agent_model import override_agent_model

__all__ = ["override_agent_model"]
