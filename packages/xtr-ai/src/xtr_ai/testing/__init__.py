"""Helpers for testing code built on xtr-ai.

:func:`override_agent_model` swaps a configured agent's model for one a test
scripts. :mod:`xtr_ai.testing.run_control_contract` holds the checks every
run-control backend passes; it imports pytest, so import it from tests only.
"""

from __future__ import annotations

from .override_agent_model import override_agent_model

__all__ = ["override_agent_model"]
