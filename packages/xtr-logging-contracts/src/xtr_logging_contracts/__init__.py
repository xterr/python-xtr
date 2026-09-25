"""The logging contract: what code that logs depends on, and nothing more.

A library that logs should not decide where records go. It takes a
:class:`LoggerInterface`, defaults to a :class:`NullLogger`, and leaves
handlers, formatters and configuration to the application that wires it — so
depending on this package costs a library nothing but the contract.

What is here is only what appears in that contract: the interface itself, the
:class:`Context` and :class:`Level` its methods accept, and the two ways of
satisfying it — :class:`AbstractLogger` to implement it in one method, and
:class:`NullLogger` to implement it in none. Everything that *acts* on what was
logged — records, handlers, processors, formatters, configuration — is
``xtr-logging``, which implements this contract and re-exports it, so the two
are never two different objects.

    from xtr_logging_contracts import LoggerInterface, NullLogger


    class Checkout:
        def __init__(self, logger: LoggerInterface | None = None) -> None:
            self._logger = logger or NullLogger()
"""

from importlib.metadata import PackageNotFoundError, version

from .abstract_logger import AbstractLogger
from .context import EXCEPTION_KEY, Context
from .exception import InvalidLevelError, LoggingError
from .level import Level, LevelLike
from .logger_aware import LoggerAware
from .logger_aware_interface import LoggerAwareInterface
from .logger_interface import LoggerInterface
from .null_logger import NullLogger
from .resettable_interface import ResettableInterface

try:
    __version__ = version("xtr-logging-contracts")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "EXCEPTION_KEY",
    "AbstractLogger",
    "Context",
    "InvalidLevelError",
    "Level",
    "LevelLike",
    "LoggerAware",
    "LoggerAwareInterface",
    "LoggerInterface",
    "LoggingError",
    "NullLogger",
    "ResettableInterface",
    "__version__",
]
