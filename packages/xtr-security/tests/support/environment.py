"""Resolving a configuration's environment placeholders the way the container does."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

from xtr_dependency_injection.config.env_placeholder import resolve_env_placeholders

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["resolved"]

T = TypeVar("T")


def resolved(config: T, environ: Mapping[str, str]) -> T:
    """Return ``config`` rebuilt with its placeholders read from ``environ``.

    What a factory closing over a configuration receives once the container
    reads the variables: a copy whose ``__post_init__`` ran again on the real
    values.
    """
    return cast("T", resolve_env_placeholders(config, environ.__getitem__))
