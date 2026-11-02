"""A RabbitMQ transport for xtr-messenger, built on its taskiq bridge.

Installed beside xtr-messenger — or as ``xtr-messenger[amqp]`` — an ``amqp://``
or ``amqps://`` DSN is served by :class:`AmqpTransportFactory`, found by its
scheme with no wiring: a connection and its queues, a retry ladder, delays
through the delayed-message exchange, and real dead-lettering.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .transport import (
    AMQP_SCHEMES,
    DEFAULT_DEAD_LETTER_QUEUE,
    AmqpTransportFactory,
    DeadLetterMiddleware,
    MixedDsnError,
    Reliability,
    create_amqp_broker,
    declared_queues,
)

try:
    __version__ = version("xtr-amqp-messenger")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "AMQP_SCHEMES",
    "DEFAULT_DEAD_LETTER_QUEUE",
    "AmqpTransportFactory",
    "DeadLetterMiddleware",
    "MixedDsnError",
    "Reliability",
    "__version__",
    "create_amqp_broker",
    "declared_queues",
]
