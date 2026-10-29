"""Unit tests for :class:`xtr_maker.entity.IdType`."""

from __future__ import annotations

import pytest

from xtr_maker.entity import IdType


@pytest.mark.parametrize(
    ("id_type", "audit", "expected"),
    [
        (IdType.UUID, True, "UUIDAuditBase"),
        (IdType.UUID, False, "UUIDBase"),
        (IdType.UUID7, True, "UUIDv7AuditBase"),
        (IdType.BIGINT, False, "BigIntBase"),
    ],
)
def test_the_key_and_the_audit_columns_pick_the_base(
    id_type: IdType, audit: bool, expected: str
) -> None:
    assert id_type.base(audit=audit) == expected


def test_an_integer_key_needs_no_import() -> None:
    assert IdType.BIGINT.python_type == ("builtins", "int")
    assert IdType.UUID7.python_type == ("uuid", "UUID")


@pytest.mark.parametrize(
    ("bases", "expected"),
    [
        (("UUIDAuditBase",), IdType.UUID),
        (("advanced_alchemy.base.UUIDv7Base",), IdType.UUID7),
        (("Mixin", "BigIntAuditBase"), IdType.BIGINT),
        (("DefaultBase",), None),
    ],
)
def test_the_key_is_told_from_the_bases(bases: tuple[str, ...], expected: IdType | None) -> None:
    assert IdType.of_bases(bases) is expected
