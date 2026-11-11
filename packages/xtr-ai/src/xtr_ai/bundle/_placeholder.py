"""Telling an ``env()`` placeholder from a value written in the configuration."""

from __future__ import annotations

from xtr_dependency_injection.config.env_placeholder import EnvPlaceholder

__all__ = ["is_literal"]


def is_literal(value: object) -> bool:
    """Whether ``value`` was written in the configuration, not read from the environment later.

    A placeholder cannot be checked while the container builds — its variable
    is read when the service needing it is built — so checks skip it and the
    service checks the value it receives.
    """
    return not isinstance(value, EnvPlaceholder)
