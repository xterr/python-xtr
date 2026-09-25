from __future__ import annotations

from xtr_logging_contracts import (
    LoggerAware,
    LoggerAwareInterface,
    LoggerInterface,
    NullLogger,
)


class Service(LoggerAware):
    pass


def test_a_logger_aware_object_starts_with_a_null_logger() -> None:
    assert isinstance(Service().logger, NullLogger)


def test_set_logger_replaces_it() -> None:
    service = Service()
    logger: LoggerInterface = NullLogger()

    service.set_logger(logger)

    assert service.logger is logger


def test_the_mixin_satisfies_the_interface() -> None:
    assert isinstance(Service(), LoggerAwareInterface)
