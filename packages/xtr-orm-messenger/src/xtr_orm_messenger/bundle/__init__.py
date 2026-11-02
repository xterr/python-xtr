"""The xtr-dependency-injection bundle for xtr-orm-messenger."""

from __future__ import annotations

from .orm_messenger_bundle import CONNECTION_PARAMETER, MAPPED_PARAMETER, OrmMessengerBundle
from .orm_messenger_config import OrmMessengerConfig

__all__ = ["CONNECTION_PARAMETER", "MAPPED_PARAMETER", "OrmMessengerBundle", "OrmMessengerConfig"]
