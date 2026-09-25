"""The bridge to the standard library's :mod:`logging`, both ways across.

Out of this library and into :mod:`logging`:

* :class:`~xtr_logging.bridge.stdlib.stdlib_handler.StdlibHandler` relays a
  channel's records to a :class:`logging.Logger`, keeping their time.

Into this library from :mod:`logging`:

* :class:`~xtr_logging.bridge.stdlib.stdlib_capture_handler.StdlibCaptureHandler`
  turns a third party's standard-library records into records on a channel, and
  :class:`~xtr_logging.bridge.stdlib.stdlib_capture.StdlibCapture` takes over
  the standard library's output with one, so no record is written twice.

And for code that wants this library's interface over a standard backend,
:class:`~xtr_logging.bridge.stdlib.stdlib_logger.StdlibLogger`. The two
directions recognise each other's records, so wiring both never loops.
"""

from .level_mapping import from_stdlib, register_level_names, to_stdlib
from .stdlib_capture import StdlibCapture
from .stdlib_capture_handler import StdlibCaptureHandler
from .stdlib_handler import StdlibHandler
from .stdlib_logger import StdlibLogger

__all__ = [
    "StdlibCapture",
    "StdlibCaptureHandler",
    "StdlibHandler",
    "StdlibLogger",
    "from_stdlib",
    "register_level_names",
    "to_stdlib",
]
