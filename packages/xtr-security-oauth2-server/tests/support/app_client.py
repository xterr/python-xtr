"""The two shapes an application's own client class can take.

An application that needs columns of its own on a client writes the class
itself, maps it with its own base, and names it in the configuration. These are
the two bases an application realistically has — a plain declarative one, where
the identifier is the primary key, and an audited one whose primary key is
already taken, where the identifier is a unique column beside it — and both
carry one column of the application's own, so the tests prove the package adds
nothing to a class it does not own.

Both classes carry the three suppressions an application's own client class
carries: a declarative base brings a constructor the model's own replaces
(``reportUnsafeMultipleInheritance``), the mixin maps columns onto the
attributes the model already declares, and the class maps one onto the
identifier the model declares (``reportIncompatibleVariableOverride``, once
for the mixin's columns and once for that identifier).
"""

from __future__ import annotations

from typing import final

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.persistence.mapping.client_mapping_mixin import ClientMappingMixin

__all__ = ["AuditAppClient", "PlainAppClient", "PlainBase"]


class PlainBase(DeclarativeBase):
    """The declarative base an application with no ORM framework of its own has."""


@final
class PlainAppClient(  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    ClientMappingMixin,
    AbstractClient,
    PlainBase,
):
    """An application's client, with the identifier as its primary key."""

    __tablename__ = "app_client"

    _identifier: Mapped[str] = mapped_column(  # pyright: ignore[reportIncompatibleVariableOverride]
        "identifier",
        String(32),
        primary_key=True,
    )
    tenant: Mapped[str | None] = mapped_column("tenant", String(32), nullable=True)


@final
class AuditAppClient(  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    ClientMappingMixin,
    AbstractClient,
    UUIDAuditBase,
):
    """An application's client on an audited base, whose primary key is its own."""

    __tablename__ = "audit_app_client"

    _identifier: Mapped[str] = mapped_column(  # pyright: ignore[reportIncompatibleVariableOverride]
        "identifier",
        String(32),
        unique=True,
        nullable=False,
    )
    tenant: Mapped[str | None] = mapped_column("tenant", String(32), nullable=True)
