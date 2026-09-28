"""Processor contract, the processors shipped with the library, and their registry."""

from __future__ import annotations

from .context_vars_processor import ContextVarsProcessor
from .hostname_processor import HostnameProcessor
from .introspection_processor import IntrospectionProcessor
from .placeholder_processor import PlaceholderProcessor
from .process_id_processor import ProcessIdProcessor
from .processor_descriptor import ProcessorDescriptor
from .processor_interface import ProcessorInterface
from .processor_registry import ProcessorRegistry, default_processor_registry
from .tag_processor import TagProcessor
from .uid_processor import UidProcessor

__all__ = [
    "ContextVarsProcessor",
    "HostnameProcessor",
    "IntrospectionProcessor",
    "PlaceholderProcessor",
    "ProcessIdProcessor",
    "ProcessorDescriptor",
    "ProcessorInterface",
    "ProcessorRegistry",
    "TagProcessor",
    "UidProcessor",
    "default_processor_registry",
]
