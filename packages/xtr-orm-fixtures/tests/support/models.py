"""Mapped classes the tests store and load."""

from __future__ import annotations

from typing import final

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "Group", "User"]


class Base(DeclarativeBase):
    pass


@final
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


@final
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
