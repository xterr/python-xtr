"""Configuration for the remote event bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["RemoteEventConfig"]


@final
@dataclass(frozen=True, slots=True)
class RemoteEventConfig:
    """What the remote event bundle builds from: nothing.

    Which consumer answers for which source is declared beside each class
    with ``as_remote_event_consumer``, where the code that consumes is — never
    in a table an application keeps in step with it by hand. That leaves this
    bundle with no value to take, so the type exists only to give the bundle
    the shape every bundle has, and to leave somewhere for a setting to go if
    one is ever needed.
    """
