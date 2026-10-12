"""The registration columns an application's own client class inherits."""

from __future__ import annotations

import pytest
from sqlalchemy import Boolean, String
from sqlalchemy.orm.exc import UnmappedClassError

from tests.support.app_client import AuditAppClient, PlainAppClient
from xtr_security_oauth2_server.persistence.mapping._fields import REGISTRATION
from xtr_security_oauth2_server.persistence.mapping.client_mapping_mixin import ClientMappingMixin
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table
from xtr_security_oauth2_server.persistence.type.grant import Grant
from xtr_security_oauth2_server.persistence.type.redirect_uri import RedirectUri
from xtr_security_oauth2_server.persistence.type.scope import Scope

_MAPPED = [PlainAppClient, AuditAppClient]
"""The application classes this mixin is mixed into, in the test support."""


def test_the_mixin_has_no_table_of_its_own() -> None:
    with pytest.raises(UnmappedClassError):
        _ = mapped_table(ClientMappingMixin)


def test_it_declares_no_identifier_of_its_own() -> None:
    assert not hasattr(ClientMappingMixin, "_identifier")


@pytest.mark.parametrize("client_class", _MAPPED)
def test_every_registration_column_lands_on_the_class_it_is_mixed_into(
    client_class: type[PlainAppClient | AuditAppClient],
) -> None:
    table = mapped_table(client_class)

    for column in REGISTRATION.values():
        assert column in table.c


@pytest.mark.parametrize("client_class", _MAPPED)
def test_every_registration_column_has_the_shape_this_package_gives_it(
    client_class: type[PlainAppClient | AuditAppClient],
) -> None:
    table = mapped_table(client_class)

    assert isinstance(table.c["name"].type, String)
    assert table.c["name"].type.length == 128
    assert table.c["name"].nullable is False
    assert isinstance(table.c["secret"].type, String)
    assert table.c["secret"].type.length == 255
    assert table.c["secret"].nullable is True
    assert isinstance(table.c["redirect_uris"].type, RedirectUri)
    assert isinstance(table.c["grants"].type, Grant)
    assert isinstance(table.c["scopes"].type, Scope)
    assert isinstance(table.c["active"].type, Boolean)
    assert table.c["active"].nullable is False
    assert table.c["allow_plain_text_pkce"].server_default is not None


@pytest.mark.parametrize("client_class", _MAPPED)
def test_the_applications_own_columns_are_left_beside_them(
    client_class: type[PlainAppClient | AuditAppClient],
) -> None:
    table = mapped_table(client_class)

    assert "identifier" in table.c
    assert "tenant" in table.c


def test_each_class_the_mixin_is_mixed_into_gets_its_own_columns() -> None:
    plain = mapped_table(PlainAppClient)
    audited = mapped_table(AuditAppClient)

    assert plain.c["name"] is not audited.c["name"]
    assert plain.c["name"].table is plain
    assert audited.c["name"].table is audited
