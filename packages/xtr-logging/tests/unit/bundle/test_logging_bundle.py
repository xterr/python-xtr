"""Unit tests for :class:`xtr_logging.bundle.LoggingBundle`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel, ServicesResetter
from xtr_dependency_injection.testing import assert_zero_config
from xtr_logging_contracts import LoggerInterface

from tests.fixtures import app_unknown_handler
from tests.fixtures.app_logging.config import HANDLER
from xtr_logging import LoggerFactory
from xtr_logging.bundle import LoggingBundle, LoggingConfig
from xtr_logging.config import ServiceHandlerSpec
from xtr_logging.exception.unknown_service_error import UnknownServiceError

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(LoggingBundle)


async def test_default_and_qualified_channels_resolve_from_the_container() -> None:
    kernel = Kernel("tests.fixtures.app_logging", env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        default_logger = await container.get(LoggerInterface)
        security_logger = await container.get(LoggerInterface, "security")
        default_logger.info("default channel")
        security_logger.notice("security channel")
    finally:
        await booted.shutdown()

    channels = [record.channel for record in HANDLER.records]
    assert "app" in channels
    assert "security" in channels


async def test_unknown_handler_id_fails_at_build() -> None:
    kernel = Kernel(
        app_unknown_handler.__name__,
        env="test",
        bundles={LoggingBundle: {"all": True}},
    )
    with pytest.raises(UnknownServiceError) as excinfo:
        _ = kernel.build()
    assert excinfo.value.service_id == "nope"


async def test_declared_processor_class_is_autoconfigured_and_attached() -> None:
    kernel = Kernel("tests.fixtures.app_logging", env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        logger = await container.get(LoggerInterface)
        logger.warning("processor hello")
    finally:
        await booted.shutdown()

    records = [record for record in HANDLER.records if record.message == "processor hello"]
    assert records, "processor test record was not recorded"
    assert records[0].extra.get("tenant") == "acme"


async def test_logger_factory_is_registered_and_reset_by_services_resetter() -> None:
    kernel = Kernel("tests.fixtures.app_logging", env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        factory = await container.get(LoggerFactory)
        assert isinstance(factory, LoggerFactory)
        resetter = await container.get(ServicesResetter)
        await resetter.reset()
    finally:
        await booted.shutdown()


def test_logging_config_is_re_exported_from_the_bundle_module() -> None:
    assert LoggingConfig is not None
    assert ServiceHandlerSpec is not None
