from __future__ import annotations

from typing import Annotated, final

import wireup
from wireup import Inject
from xtr_logging_contracts import LoggerInterface

from xtr_logging import Logger, TestHandler
from xtr_logging.config import LoggingConfig, ServiceHandlerSpec, Services
from xtr_logging.integration import wireup as logging_integration
from xtr_logging.logger_factory import LoggerFactory
from xtr_logging.processor.processor_registry import ProcessorRegistry


@final
@wireup.injectable
class Checkout:
    def __init__(
        self,
        logger: LoggerInterface,
        audit: Annotated[LoggerInterface, Inject(qualifier="security")],
    ) -> None:
        self.logger = logger
        self.audit = audit


def _factory(handler: TestHandler) -> LoggerFactory:
    return LoggerFactory(
        LoggingConfig(channels=("security",), handlers={"main": ServiceHandlerSpec(id="main")}),
        services=Services(handlers={"main": handler}),
        registry=ProcessorRegistry(),
    )


def test_a_service_receives_the_default_and_a_qualified_channel() -> None:
    handler = TestHandler()
    container = wireup.create_sync_container(
        injectables=[Checkout, *logging_integration.injectables(_factory(handler))],
    )

    checkout = container.get(Checkout)
    checkout.logger.info("paid")
    checkout.audit.notice("card used")

    assert [(r.channel, r.message) for r in handler.records] == [
        ("app", "paid"),
        ("security", "card used"),
    ]


def test_the_factory_itself_is_provided() -> None:
    factory = _factory(TestHandler())
    container = wireup.create_sync_container(injectables=logging_integration.injectables(factory))

    assert container.get(LoggerFactory) is factory


def test_a_config_is_built_into_a_factory() -> None:
    container = wireup.create_sync_container(
        injectables=logging_integration.injectables(LoggingConfig(), registry=ProcessorRegistry()),
    )

    logger = container.get(LoggerInterface)
    assert isinstance(logger, Logger)
    assert logger.name == "app"
