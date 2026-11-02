from __future__ import annotations

from xtr_messenger import MessageBusError

from xtr_orm_messenger import InvalidOrmDsnError, OrmMessengerError, TransportError


def test_every_error_is_a_message_bus_error() -> None:
    assert issubclass(OrmMessengerError, MessageBusError)
    assert issubclass(TransportError, OrmMessengerError)
    assert issubclass(InvalidOrmDsnError, OrmMessengerError)
    assert issubclass(InvalidOrmDsnError, LookupError)


def test_a_transport_error_names_the_transport_and_the_operation() -> None:
    error = TransportError("orders", "get messages", "deadlock detected")

    assert (error.transport, error.operation, error.reason) == (
        "orders",
        "get messages",
        "deadlock detected",
    )
    assert str(error) == 'The "orders" transport could not get messages: deadlock detected.'


def test_an_invalid_dsn_error_with_no_connections_says_so() -> None:
    error = InvalidOrmDsnError("orders", "main", ())

    assert str(error).endswith("the connections are: none.")
