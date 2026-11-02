"""The ``orm://`` transport: messages kept in a table on an xtr-orm connection."""

from __future__ import annotations

from .connection import LISTING_PAGE_SIZE, Connection
from .messages_table import messages_table
from .messages_table_driver import MessagesTableDriver
from .messages_tables import messages_tables
from .orm_options import DEFAULT_QUEUE, DEFAULT_TABLE_NAME, ORM_OPTIONS, ORM_SCHEME, OrmOptions
from .orm_received_stamp import OrmReceivedStamp
from .orm_receiver import MAX_RETRIES, RECONNECT_TIMEOUT, OrmReceiver
from .orm_sender import OrmSender
from .orm_transport import OrmTransport
from .orm_transport_factory import OrmTransportFactory
from .postgresql_notifier import PostgreSqlNotifier
from .stored_message import StoredMessage

__all__ = [
    "DEFAULT_QUEUE",
    "DEFAULT_TABLE_NAME",
    "LISTING_PAGE_SIZE",
    "MAX_RETRIES",
    "ORM_OPTIONS",
    "ORM_SCHEME",
    "RECONNECT_TIMEOUT",
    "Connection",
    "MessagesTableDriver",
    "OrmOptions",
    "OrmReceivedStamp",
    "OrmReceiver",
    "OrmSender",
    "OrmTransport",
    "OrmTransportFactory",
    "PostgreSqlNotifier",
    "StoredMessage",
    "messages_table",
    "messages_tables",
]
