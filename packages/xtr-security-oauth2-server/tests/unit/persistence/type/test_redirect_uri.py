"""Registered redirect URIs stored as one space-joined string, and read back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.dialects import sqlite

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri as RedirectUriValue

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()


def test_redirect_uris_go_in_space_joined() -> None:
    bound = RedirectUri().process_bind_param(
        (RedirectUriValue("https://app.example.com/cb"), RedirectUriValue("com.example.app:/cb")),
        _DIALECT,
    )

    assert bound == "https://app.example.com/cb com.example.app:/cb"


def test_a_stored_string_comes_back_as_redirect_uris() -> None:
    read = RedirectUri().process_result_value("https://app.example.com/cb", _DIALECT)

    assert read == (RedirectUriValue("https://app.example.com/cb"),)


def test_no_redirect_uri_stored_comes_back_as_none_registered() -> None:
    assert RedirectUri().process_result_value(None, _DIALECT) == ()


async def test_redirect_uris_survive_a_trip_through_a_database(tmp_path: Path) -> None:
    registered = (
        RedirectUriValue("https://app.example.com/cb"),
        RedirectUriValue("com.example.app:/cb"),
    )

    assert await round_trip(tmp_path, RedirectUri(), registered) == registered


async def test_a_client_with_no_redirect_uri_survives_a_trip(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, RedirectUri(), ()) == ()
