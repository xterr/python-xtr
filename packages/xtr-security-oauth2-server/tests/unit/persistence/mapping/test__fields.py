"""Which column of a table each attribute of a model is kept in."""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, String, Table

from tests.support.models import LATER, client_model, device_code_model
from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.persistence.mapping._fields import (
    BESIDE,
    CLIENT,
    CREDENTIAL,
    DEVICE_CODE,
    HOLDER,
    REFRESH_TOKEN,
    REGISTRATION,
    columns,
)
from xtr_security_oauth2_server.value_object.scope import Scope


def _table() -> Table:
    return Table(
        "two",
        MetaData(),
        Column("identifier", String(8), primary_key=True),
        Column("interval", Integer(), nullable=False),
    )


def test_it_answers_with_the_column_each_attribute_is() -> None:
    table = _table()

    mapped = columns(table, {"_identifier": "identifier", "_interval": "interval"})

    assert mapped == {
        "_identifier": table.c["identifier"],
        "_interval": table.c["interval"],
    }


def test_naming_nothing_maps_nothing() -> None:
    assert columns(_table(), {}) == {}


def test_the_shipped_client_adds_its_identifier_to_the_registration() -> None:
    assert set(CLIENT) == {*REGISTRATION, "_identifier"}


def test_every_registration_attribute_is_one_a_client_keeps() -> None:
    client = client_model()

    for attribute in REGISTRATION:
        assert hasattr(client, attribute)


def test_every_credential_attribute_is_one_an_access_token_keeps() -> None:
    token = AccessToken("at-1", LATER, client_model(), None, (Scope("read"),))

    for attribute in CREDENTIAL:
        assert hasattr(token, attribute)


def test_every_device_code_attribute_is_one_a_device_code_keeps() -> None:
    code = device_code_model()

    for attribute in {**CREDENTIAL, **DEVICE_CODE}:
        assert hasattr(code, attribute)


def test_every_refresh_token_attribute_is_one_a_refresh_token_keeps() -> None:
    token = RefreshToken("rt-1", LATER)

    for attribute in REFRESH_TOKEN:
        assert hasattr(token, attribute)


def test_a_refresh_token_keeps_neither_a_user_nor_a_scope() -> None:
    assert "_user_identifier" not in REFRESH_TOKEN
    assert "_scopes" not in REFRESH_TOKEN


def test_the_names_a_relationship_is_written_through_are_private_and_its_own() -> None:
    assert HOLDER.startswith("_")
    assert BESIDE.startswith("_")
    assert HOLDER not in CREDENTIAL
    assert BESIDE not in REFRESH_TOKEN
    assert not hasattr(AbstractClient("Name", "client-1", None), HOLDER)
