"""A database transport for xtr-messenger, on the connections xtr-orm configures.

Messages are kept in a table on one of the application's connections, named by
the DSN — ``orm://default``. A worker claims the oldest one of its queue that
is due, a delayed one falls due when its delay has passed, a message whose
worker died is handed out again, and on PostgreSQL a waiting worker is woken
the moment a message is sent.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import InvalidOrmDsnError, OrmMessengerError, TransportError
from .transport import (
    DEFAULT_QUEUE,
    DEFAULT_TABLE_NAME,
    ORM_OPTIONS,
    ORM_SCHEME,
    Connection,
    OrmOptions,
    OrmReceivedStamp,
    OrmReceiver,
    OrmSender,
    OrmTransport,
    OrmTransportFactory,
    StoredMessage,
    messages_table,
)

try:
    __version__ = version("xtr-orm-messenger")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "DEFAULT_QUEUE",
    "DEFAULT_TABLE_NAME",
    "ORM_OPTIONS",
    "ORM_SCHEME",
    "Connection",
    "InvalidOrmDsnError",
    "OrmMessengerError",
    "OrmOptions",
    "OrmReceivedStamp",
    "OrmReceiver",
    "OrmSender",
    "OrmTransport",
    "OrmTransportFactory",
    "StoredMessage",
    "TransportError",
    "__version__",
    "messages_table",
]
