"""The columns of every table this package keeps a client or a credential in."""

from __future__ import annotations

from sqlalchemy import CHAR, MetaData, String

from xtr_security_oauth2_server.persistence.mapping._tables import (
    CREDENTIAL,
    IDENTIFIER,
    NAME,
    REGISTRATION_COLUMNS,
    SECRET,
    URI,
    access_token_table,
    authorization_code_table,
    client_table,
    device_code_table,
    refresh_token_table,
)


def test_a_table_joins_the_definitions_it_is_given() -> None:
    metadata = MetaData()

    built = client_table(metadata, "oauth2_")

    assert metadata.tables["oauth2_client"] is built


def test_the_prefix_starts_every_tables_name() -> None:
    metadata = MetaData()

    names = {
        client_table(metadata, "srv_").name,
        authorization_code_table(metadata, "srv_", "srv_client").name,
        access_token_table(metadata, "srv_", "srv_client").name,
        device_code_table(metadata, "srv_", "srv_client").name,
        refresh_token_table(metadata, "srv_", beside_access_token=True).name,
    }

    assert names == {
        "srv_client",
        "srv_authorization_code",
        "srv_access_token",
        "srv_device_code",
        "srv_refresh_token",
    }


def test_a_credential_points_at_the_client_table_it_was_told_about() -> None:
    metadata = MetaData()

    built = access_token_table(metadata, "oauth2_", "app_client")
    key = next(iter(built.c["client"].foreign_keys))

    assert key.target_fullname == "app_client.identifier"
    assert key.ondelete == "CASCADE"


def test_the_refresh_token_table_names_an_access_token_only_where_there_is_one() -> None:
    with_token = refresh_token_table(MetaData(), "oauth2_", beside_access_token=True)
    without = refresh_token_table(MetaData(), "oauth2_", beside_access_token=False)

    assert "access_token" in with_token.c
    assert "access_token" not in without.c


def test_a_client_identifier_and_a_name_are_as_long_as_declared() -> None:
    clients = client_table(MetaData(), "oauth2_")
    identifier = clients.c["identifier"].type
    name = clients.c["name"].type
    secret = clients.c["secret"].type

    assert isinstance(identifier, String)
    assert isinstance(name, String)
    assert isinstance(secret, String)
    assert (identifier.length, name.length, secret.length) == (IDENTIFIER, NAME, SECRET)


def test_a_credential_identifier_and_a_user_code_are_as_long_as_declared() -> None:
    metadata = MetaData()
    codes = device_code_table(metadata, "oauth2_", "oauth2_client")
    identifier = codes.c["identifier"].type
    user_code = codes.c["user_code"].type

    assert isinstance(identifier, CHAR)
    assert isinstance(user_code, String)
    assert (identifier.length, user_code.length) == (CREDENTIAL, URI)


def test_the_client_table_holds_every_registration_column_described() -> None:
    clients = client_table(MetaData(), "oauth2_")

    assert [column.name for column in REGISTRATION_COLUMNS] == [
        column.name for column in clients.c if column.name != "identifier"
    ]


def test_a_registration_column_is_its_own_object_in_every_table_built() -> None:
    first = client_table(MetaData(), "oauth2_")
    second = client_table(MetaData(), "srv_")

    assert first.c["name"] is not second.c["name"]
    assert second.c["name"].table is second
