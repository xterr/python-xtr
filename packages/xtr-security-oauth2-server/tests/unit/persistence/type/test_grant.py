"""A client's grants stored as one space-joined string, and read back as grants."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.dialects import sqlite

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.grant import Grant
from xtr_security_oauth2_server.value_object.grant import Grant as GrantValue

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()


def test_grants_go_in_space_joined() -> None:
    bound = Grant().process_bind_param(
        (GrantValue("authorization_code"), GrantValue("refresh_token")),
        _DIALECT,
    )

    assert bound == "authorization_code refresh_token"


def test_a_stored_string_comes_back_as_grants() -> None:
    assert Grant().process_result_value("client_credentials", _DIALECT) == (
        GrantValue("client_credentials"),
    )


def test_no_grant_stored_comes_back_as_no_grant() -> None:
    assert Grant().process_result_value(None, _DIALECT) == ()


async def test_grants_survive_a_trip_through_a_database(tmp_path: Path) -> None:
    allowed = (GrantValue("authorization_code"), GrantValue("refresh_token"))

    assert await round_trip(tmp_path, Grant(), allowed) == allowed


async def test_a_client_allowed_every_grant_survives_a_trip(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, Grant(), ()) == ()
