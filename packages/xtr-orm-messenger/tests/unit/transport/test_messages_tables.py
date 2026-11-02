from __future__ import annotations

import pytest
from xtr_messenger import MessageBusConfig, TransportConfig, UnknownTransportOptionError

from xtr_orm_messenger.transport import messages_tables


def test_it_names_the_table_of_every_orm_transport_on_the_connection() -> None:
    config = MessageBusConfig(
        transports={
            "jobs": TransportConfig("orm://default", queue="jobs"),
            "audit": TransportConfig("orm://default?table_name=audit_messages"),
            "reports": TransportConfig("orm://reports"),
            "sync": TransportConfig("sync://"),
        }
    )

    assert messages_tables(config, "default", "default") == ("messenger_messages", "audit_messages")
    assert messages_tables(config, "reports", "default") == ("messenger_messages",)


def test_a_transport_naming_no_connection_is_on_the_default_one() -> None:
    config = MessageBusConfig(transports={"jobs": TransportConfig("orm://")})

    assert messages_tables(config, "main", "main") == ("messenger_messages",)
    assert messages_tables(config, "default", "main") == ()


def test_transports_sharing_a_table_name_it_once() -> None:
    config = MessageBusConfig(
        transports={
            "high": TransportConfig("orm://default", queue="high"),
            "low": TransportConfig("orm://default", queue="low"),
        }
    )

    assert messages_tables(config, "default", "default") == ("messenger_messages",)


def test_a_bus_with_no_orm_transport_has_no_table() -> None:
    assert messages_tables(MessageBusConfig(), "default", "default") == ()


def test_a_setting_the_transport_does_not_take_is_refused() -> None:
    config = MessageBusConfig(transports={"jobs": TransportConfig("orm://default?exchange=x")})

    with pytest.raises(UnknownTransportOptionError):
        _ = messages_tables(config, "default", "default")
