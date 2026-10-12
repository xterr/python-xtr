"""What the driver builds and what it maps, for each shape of deployment."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import CHAR, MetaData, String
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from xtr_orm.mapping_driver_interface import MappingDriverInterface
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from tests.support.app_client import AuditAppClient, PlainAppClient
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.persistence.mapping.driver import Driver
from xtr_security_oauth2_server.persistence.type.grant import Grant
from xtr_security_oauth2_server.persistence.type.redirect_uri import RedirectUri
from xtr_security_oauth2_server.persistence.type.scope import Scope
from xtr_security_oauth2_server.persistence.type.utc_datetime import UtcDateTime

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Table


@contextmanager
def _loaded(driver: Driver, metadata: MetaData | None = None) -> Generator[MetaData, None, None]:
    """Load ``driver`` into definitions, then unmap what it mapped.

    The mapping lives on the model classes, which the process shares, so a
    test that left it behind would decide what the next one is mapped against.
    """
    definitions = metadata if metadata is not None else MetaData()
    _ = driver.load_metadata(definitions)
    try:
        yield definitions
    finally:
        driver._dispose()


def test_it_declares_the_mapping_driver_contract() -> None:
    assert MappingDriverInterface in Driver.__mro__


def _length(table: Table, column: str) -> int | None:
    """Return how long the string column ``column`` of ``table`` may be."""
    return cast("String | CHAR", table.c[column].type).length


def _target(table: Table, column: str) -> tuple[str, str | None]:
    """Return what ``column`` points at, and what happens when that row goes."""
    key = next(iter(table.c[column].foreign_keys))

    return key.target_fullname, key.ondelete


def test_every_table_of_a_full_deployment_is_loaded() -> None:
    with _loaded(Driver(Client, True)) as metadata:
        assert set(metadata.tables) == {
            "oauth2_client",
            "oauth2_access_token",
            "oauth2_authorization_code",
            "oauth2_refresh_token",
            "oauth2_device_code",
        }


def test_the_device_code_table_is_left_out_only_where_the_flow_is_turned_off() -> None:
    with _loaded(Driver(Client, True, "oauth2_", False)) as metadata:
        assert "oauth2_device_code" not in metadata.tables
        assert "oauth2_authorization_code" in metadata.tables


def test_the_access_token_table_is_loaded_only_where_tokens_are_persisted() -> None:
    with _loaded(Driver(Client, False)) as metadata:
        assert "oauth2_access_token" not in metadata.tables
        assert "oauth2_authorization_code" in metadata.tables


def test_a_refresh_token_points_at_an_access_token_only_where_there_is_one() -> None:
    with _loaded(Driver(Client, False)) as metadata:
        assert "access_token" not in metadata.tables["oauth2_refresh_token"].c


def test_the_prefix_names_every_table() -> None:
    with _loaded(Driver(Client, True, "srv_")) as metadata:
        assert set(metadata.tables) == {
            "srv_client",
            "srv_access_token",
            "srv_authorization_code",
            "srv_refresh_token",
            "srv_device_code",
        }


def test_the_names_loaded_are_the_ones_reported() -> None:
    driver = Driver(Client, True)
    metadata = MetaData()
    try:
        added = driver.load_metadata(metadata)

        assert set(added) == set(metadata.tables)
    finally:
        driver._dispose()


def test_loading_twice_adds_nothing_and_reports_nothing() -> None:
    driver = Driver(Client, True)
    metadata = MetaData()
    try:
        _ = driver.load_metadata(metadata)
        before = set(metadata.tables)

        assert driver.load_metadata(metadata) == ()
        assert set(metadata.tables) == before
    finally:
        driver._dispose()


def test_the_client_table_holds_the_registration_a_client_is_given() -> None:
    with _loaded(Driver(Client, True)) as metadata:
        clients = metadata.tables["oauth2_client"]

        assert clients.c["identifier"].primary_key is True
        assert _length(clients, "identifier") == 32
        assert _length(clients, "name") == 128
        assert clients.c["name"].nullable is False
        assert _length(clients, "secret") == 255
        assert clients.c["secret"].nullable is True
        assert isinstance(clients.c["redirect_uris"].type, RedirectUri)
        assert isinstance(clients.c["grants"].type, Grant)
        assert isinstance(clients.c["scopes"].type, Scope)
        assert clients.c["active"].nullable is False
        assert clients.c["allow_plain_text_pkce"].server_default is not None


@pytest.mark.parametrize(
    "name",
    ["oauth2_access_token", "oauth2_authorization_code", "oauth2_device_code"],
)
def test_a_credential_table_holds_who_it_is_for_and_until_when(name: str) -> None:
    with _loaded(Driver(Client, True)) as metadata:
        credentials = metadata.tables[name]

        assert credentials.c["identifier"].primary_key is True
        assert isinstance(credentials.c["identifier"].type, CHAR)
        assert _length(credentials, "identifier") == 80
        assert isinstance(credentials.c["expiry"].type, UtcDateTime)
        assert credentials.c["expiry"].nullable is False
        assert _length(credentials, "user_identifier") == 128
        assert credentials.c["user_identifier"].nullable is True
        assert isinstance(credentials.c["scopes"].type, Scope)
        assert credentials.c["revoked"].nullable is False
        assert credentials.c["client"].nullable is False
        assert _target(credentials, "client") == ("oauth2_client.identifier", "CASCADE")


def test_the_device_code_table_holds_the_state_a_live_flow_writes() -> None:
    with _loaded(Driver(Client, True)) as metadata:
        codes = metadata.tables["oauth2_device_code"]

        assert _length(codes, "user_code") == 255
        assert codes.c["user_code"].nullable is True
        assert codes.c["user_approved"].nullable is False
        assert codes.c["include_verification_uri_complete"].nullable is False
        assert _length(codes, "verification_uri") == 255
        assert codes.c["verification_uri"].nullable is True
        assert isinstance(codes.c["last_polled_at"].type, UtcDateTime)
        assert codes.c["last_polled_at"].nullable is True
        assert codes.c["interval"].nullable is False


def test_the_refresh_token_table_loses_its_access_token_rather_than_going_with_it() -> None:
    with _loaded(Driver(Client, True)) as metadata:
        tokens = metadata.tables["oauth2_refresh_token"]

        assert tokens.c["identifier"].primary_key is True
        assert _length(tokens, "identifier") == 80
        assert isinstance(tokens.c["expiry"].type, UtcDateTime)
        assert tokens.c["revoked"].nullable is False
        assert tokens.c["access_token"].nullable is True
        assert _target(tokens, "access_token") == ("oauth2_access_token.identifier", "SET NULL")


def test_no_client_table_is_built_for_a_client_the_application_maps() -> None:
    with _loaded(Driver(PlainAppClient, True), PlainAppClient.metadata) as metadata:
        assert "oauth2_client" not in metadata.tables
        assert _target(metadata.tables["oauth2_access_token"], "client") == (
            "app_client.identifier",
            "CASCADE",
        )


def test_a_credential_points_at_the_identifier_of_an_audited_application_client() -> None:
    with _loaded(Driver(AuditAppClient, True), AuditAppClient.metadata) as metadata:
        assert _target(metadata.tables["oauth2_authorization_code"], "client") == (
            "audit_app_client.identifier",
            "CASCADE",
        )


def test_every_model_of_a_full_deployment_is_mapped() -> None:
    with _loaded(Driver(Client, True)):
        for model in (Client, AccessToken, AuthorizationCode, RefreshToken, DeviceCode):
            assert class_mapper(model) is not None


def test_a_model_the_deployment_turned_off_is_left_unmapped() -> None:
    with _loaded(Driver(Client, False)), pytest.raises(UnmappedClassError):
        _ = class_mapper(AccessToken)


def test_a_device_code_is_left_unmapped_without_the_device_flow() -> None:
    with _loaded(Driver(Client, True, "oauth2_", False)), pytest.raises(UnmappedClassError):
        _ = class_mapper(DeviceCode)


def test_the_shipped_client_is_mapped_only_when_it_is_the_one_configured() -> None:
    with (
        _loaded(Driver(PlainAppClient, True), PlainAppClient.metadata),
        pytest.raises(UnmappedClassError),
    ):
        _ = class_mapper(Client)


def test_a_model_already_mapped_to_the_same_table_is_left_alone() -> None:
    driver = Driver(Client, True)
    metadata = MetaData()
    try:
        _ = driver.load_metadata(metadata)
        mapped = class_mapper(AccessToken)

        _ = driver.load_metadata(metadata)

        assert class_mapper(AccessToken) is mapped
    finally:
        driver._dispose()


def test_a_model_already_mapped_to_another_table_is_refused_naming_both() -> None:
    first = Driver(Client, True)
    second = Driver(Client, True, "srv_")
    try:
        _ = first.load_metadata(MetaData())

        with pytest.raises(InvalidArgumentError) as refused:
            _ = second.load_metadata(MetaData())

        assert "Client" in str(refused.value)
        assert "oauth2_client" in str(refused.value)
        assert "srv_client" in str(refused.value)
    finally:
        second._dispose()
        first._dispose()


def test_a_credential_already_mapped_to_another_table_is_refused_naming_both() -> None:
    first = Driver(PlainAppClient, True)
    second = Driver(PlainAppClient, True, "srv_")
    try:
        _ = first.load_metadata(PlainAppClient.metadata)

        with pytest.raises(InvalidArgumentError) as refused:
            _ = second.load_metadata(MetaData())

        assert "AuthorizationCode" in str(refused.value)
        assert "oauth2_authorization_code" in str(refused.value)
        assert "srv_authorization_code" in str(refused.value)
    finally:
        second._dispose()
        first._dispose()


def test_disposing_unmaps_what_the_driver_mapped() -> None:
    driver = Driver(Client, True)
    _ = driver.load_metadata(MetaData())

    driver._dispose()

    with pytest.raises(UnmappedClassError):
        _ = class_mapper(AccessToken)


def test_disposing_leaves_the_client_the_application_maps_alone() -> None:
    driver = Driver(PlainAppClient, True)
    _ = driver.load_metadata(PlainAppClient.metadata)

    driver._dispose()

    assert class_mapper(PlainAppClient) is not None


def test_a_disposed_driver_can_be_loaded_again() -> None:
    driver = Driver(Client, True)
    metadata = MetaData()
    _ = driver.load_metadata(metadata)
    driver._dispose()
    try:
        _ = driver.load_metadata(MetaData())

        assert class_mapper(AccessToken) is not None
    finally:
        driver._dispose()


def test_disposing_puts_back_the_default_the_mapping_stood_in_for() -> None:
    driver = Driver(Client, True)
    _ = driver.load_metadata(MetaData())

    driver._dispose()

    assert RefreshToken.__dict__["_access_token"] is None


def test_disposing_leaves_what_the_mapping_never_replaced_untouched() -> None:
    driver = Driver(Client, True)
    declared: dict[str, object] = dict(vars(RefreshToken))
    untouched = {name: value for name, value in declared.items() if name != "_access_token"}

    _ = driver.load_metadata(MetaData())
    driver._dispose()

    found: dict[str, object] = dict(vars(RefreshToken))
    assert {name: found.get(name) for name in untouched} == untouched
