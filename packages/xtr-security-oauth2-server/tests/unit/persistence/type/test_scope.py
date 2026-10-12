"""Granted scopes stored as one space-joined string, and read back as scopes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.dialects import sqlite

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.scope import Scope
from xtr_security_oauth2_server.value_object.scope import Scope as ScopeValue

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()


def test_scopes_go_in_space_joined_the_way_a_token_carries_them() -> None:
    bound = Scope().process_bind_param((ScopeValue("read"), ScopeValue("write")), _DIALECT)

    assert bound == "read write"


def test_a_stored_string_comes_back_as_scopes() -> None:
    assert Scope().process_result_value("read write", _DIALECT) == (
        ScopeValue("read"),
        ScopeValue("write"),
    )


def test_no_scope_stored_comes_back_as_no_scope() -> None:
    assert Scope().process_result_value(None, _DIALECT) == ()


async def test_scopes_survive_a_trip_through_a_database(tmp_path: Path) -> None:
    granted = (ScopeValue("read"), ScopeValue("write"))

    assert await round_trip(tmp_path, Scope(), granted) == granted


async def test_a_scopeless_token_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, Scope(), ()) == ()
