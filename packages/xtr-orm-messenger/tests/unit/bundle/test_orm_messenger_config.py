from __future__ import annotations

import pytest
from xtr_messenger import InvalidTransportOptionError

from xtr_orm_messenger.bundle import OrmMessengerConfig


def test_it_builds_with_no_arguments_and_maps_nothing() -> None:
    config = OrmMessengerConfig()

    assert (config.migrations_connection, config.table_name) == (None, "messenger_messages")


def test_a_table_name_no_transport_could_use_is_refused() -> None:
    with pytest.raises(InvalidTransportOptionError):
        _ = OrmMessengerConfig(table_name="my-messages")


def test_an_empty_connection_name_is_refused() -> None:
    with pytest.raises(ValueError, match="names no connection"):
        _ = OrmMessengerConfig(migrations_connection="")
