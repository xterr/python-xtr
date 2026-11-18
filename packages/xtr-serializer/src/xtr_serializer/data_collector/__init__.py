"""The serializer's profiler panel: every call a profiled request made on a serializer.

A :class:`TraceableSerializer` wraps a serializer and records each call into a request trace;
:class:`SerializerDataCollector` reads that trace into the profile. The bundle wires both when
the http kernel's profiler is on. Importing this needs xtr-http-kernel and xtr-clock installed.
"""

from __future__ import annotations

from .serializer_call import SerializerCall
from .serializer_data_collector import SerializerDataCollector
from .traceable_serializer import TraceableSerializer

__all__ = ["SerializerCall", "SerializerDataCollector", "TraceableSerializer"]
