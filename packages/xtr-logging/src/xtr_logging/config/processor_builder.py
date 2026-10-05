"""Turning a processor configuration into a processor."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.processor.context_vars_processor import ContextVarsProcessor
from xtr_logging.processor.hostname_processor import HostnameProcessor
from xtr_logging.processor.introspection_processor import IntrospectionProcessor
from xtr_logging.processor.placeholder_processor import PlaceholderProcessor
from xtr_logging.processor.process_id_processor import ProcessIdProcessor
from xtr_logging.processor.tag_processor import TagProcessor
from xtr_logging.processor.uid_processor import UidProcessor

from .processor_configs import (
    ContextVarsProcessorConfig,
    HostnameProcessorConfig,
    IntrospectionProcessorConfig,
    PlaceholderProcessorConfig,
    ProcessIdProcessorConfig,
    ServiceProcessorConfig,
    TagProcessorConfig,
    UidProcessorConfig,
)

if TYPE_CHECKING:
    from xtr_logging.processor.processor_interface import ProcessorInterface

    from .processor_configs import ProcessorConfig
    from .services import Services

__all__ = ["build_processor"]


def build_processor(config: ProcessorConfig, services: Services) -> ProcessorInterface:  # noqa: PLR0911 — one case per processor type
    """Build the processor ``config`` describes, or look up the service it names.

    Raises:
        UnknownServiceError: If ``config`` names a processor that was not supplied.
        InvalidOptionError: If an option is out of range.
    """
    match config:
        case PlaceholderProcessorConfig():
            return PlaceholderProcessor(
                config.date_format,
                remove_used_context_fields=config.remove_used_context_fields,
            )
        case UidProcessorConfig():
            return UidProcessor(config.length)
        case HostnameProcessorConfig():
            return HostnameProcessor()
        case ProcessIdProcessorConfig():
            return ProcessIdProcessor()
        case IntrospectionProcessorConfig():
            return IntrospectionProcessor(
                config.level,
                skip_module_prefixes=config.skip_module_prefixes,
                skip_frames=config.skip_frames,
            )
        case TagProcessorConfig():
            return TagProcessor(config.tags)
        case ContextVarsProcessorConfig():
            return ContextVarsProcessor(config.key)
        case ServiceProcessorConfig():
            found = services.processors.get(config.id)
            if found is None:
                raise UnknownServiceError("processor", config.id, tuple(services.processors))
            return found
        case _:
            # A configuration added to the union without a case fails here, not on a first record.
            assert_never(config)
