"""Turning a processor spec into a processor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.processor.context_vars_processor import ContextVarsProcessor
from xtr_logging.processor.hostname_processor import HostnameProcessor
from xtr_logging.processor.introspection_processor import IntrospectionProcessor
from xtr_logging.processor.placeholder_processor import PlaceholderProcessor
from xtr_logging.processor.process_id_processor import ProcessIdProcessor
from xtr_logging.processor.tag_processor import TagProcessor
from xtr_logging.processor.uid_processor import UidProcessor

from .processor_specs import (
    ContextVarsProcessorSpec,
    HostnameProcessorSpec,
    IntrospectionProcessorSpec,
    PlaceholderProcessorSpec,
    ProcessIdProcessorSpec,
    ServiceProcessorSpec,
    TagProcessorSpec,
    UidProcessorSpec,
)

if TYPE_CHECKING:
    from xtr_logging.processor.processor_interface import ProcessorInterface

    from .processor_specs import ProcessorSpec
    from .services import Services

__all__ = ["build_processor"]


def build_processor(spec: ProcessorSpec, services: Services) -> ProcessorInterface:  # noqa: PLR0911 — one case per processor type
    """Build the processor ``spec`` describes, or look up the service it names.

    Raises:
        UnknownServiceError: If ``spec`` names a processor that was not supplied.
        InvalidOptionError: If an option is out of range.
    """
    match spec:
        case PlaceholderProcessorSpec():
            return PlaceholderProcessor(
                spec.date_format,
                remove_used_context_fields=spec.remove_used_context_fields,
            )
        case UidProcessorSpec():
            return UidProcessor(spec.length)
        case HostnameProcessorSpec():
            return HostnameProcessor()
        case ProcessIdProcessorSpec():
            return ProcessIdProcessor()
        case IntrospectionProcessorSpec():
            return IntrospectionProcessor(
                spec.level,
                skip_module_prefixes=spec.skip_module_prefixes,
                skip_frames=spec.skip_frames,
            )
        case TagProcessorSpec():
            return TagProcessor(spec.tags)
        case ContextVarsProcessorSpec():
            return ContextVarsProcessor(spec.key)
        case ServiceProcessorSpec():
            found = services.processors.get(spec.id)
            if found is None:
                raise UnknownServiceError("processor", spec.id, tuple(services.processors))
            return found
