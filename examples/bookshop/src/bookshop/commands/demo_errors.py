"""``demo:errors`` — trigger, catch and print the guided errors of every package.

Every error each package raises derives from one base per package (``DependencyInjectionError``,
``ConsoleError``, ``MessageBusError``, ``LoggingError``, ``ClockError``, ``DotenvError``) and
carries its data as typed attributes. Nothing here lets an error escape: each case is run,
caught, and reported as a row.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import final
from uuid import uuid4

from pydantic import ValidationError
from xtr_clock import InvalidModifierError, InvalidTimezoneError, now, resolve_timezone
from xtr_clock.bundle import ClockBundle
from xtr_console import (
    CommandsLocator,
    ConsoleStyle,
    DuplicateCommandError,
    ExitCode,
    InvalidDefaultError,
    as_command,
    escape,
)
from xtr_dependency_injection import ContainerBagInterface, Kernel
from xtr_dependency_injection.exception import DependencyInjectionError
from xtr_dotenv import Dotenv, DotenvError
from xtr_logging import LoggerFactory
from xtr_logging_contracts import Level, LoggingError
from xtr_messenger import (
    ErrorDetailsStamp,
    HandlersLocator,
    InMemoryTransport,
    MessageBusConfig,
    MessageBusError,
    MessageBusInterface,
    TransportConfig,
    TransportFactory,
    WorkerFactory,
    as_message_handler,
)
from xtr_service_contracts import ContainerInterface

from bookshop.diagnostics.misconfigured import NeedsANumber, NeedsAnUnsetVariable
from bookshop.kernel import kernel
from bookshop.messaging.messages import AuditEvent, ReindexCatalog, SendReceipt
from bookshop.notifications.notifiers import SmsNotifier
from bookshop.ordering import UnitOfWork
from bookshop.reporting import ExportRegistry

__all__ = ["DemoErrorsCommand"]

Case = Callable[[], Awaitable[object]]
_EXPECTED = (
    DependencyInjectionError,
    MessageBusError,
    LoggingError,
    DotenvError,
    InvalidModifierError,
    InvalidTimezoneError,
    DuplicateCommandError,
    InvalidDefaultError,
    ValidationError,
    LookupError,
)


@final
@as_command("demo:errors")
class DemoErrorsCommand:
    """Run every failure case and print what each raised."""

    def __init__(  # noqa: PLR0913, PLR0917 — every collaborator a failure case needs.
        self,
        container: ContainerInterface,
        parameters: ContainerBagInterface,
        exporters: ExportRegistry,
        bus: MessageBusInterface,
        workers: WorkerFactory,
        transports: TransportFactory,
        config: MessageBusConfig,
        factory: LoggerFactory,
    ) -> None:
        """Keep the collaborators."""
        self._container = container
        self._parameters = parameters
        self._exporters = exporters
        self._bus = bus
        self._workers = workers
        self._transports = transports
        self._config = config
        self._factory = factory

    async def __call__(self, io: ConsoleStyle) -> int:
        """Run every case.

        Args:
            io: Where the command writes.
        """
        rows: list[list[str]] = []
        for label, case in self._cases(io).items():
            try:
                outcome = await case()
            except _EXPECTED as error:
                cause = error.__cause__
                raised = type(error).__name__ + (f" <- {type(cause).__name__}" if cause else "")
                rows.append([label, raised, escape(str(error).splitlines()[0])[:90]])
            else:
                rows.append([label, "(no error)", escape(str(outcome))[:90]])
        io.title("Guided errors")
        io.table(["Case", "Raised", "Message"], rows)
        return ExitCode.SUCCESS

    def _cases(self, io: ConsoleStyle) -> dict[str, Case]:
        return {
            # ---- dependency injection: at runtime ------------------------------------
            "env var unset": lambda: self._container.get(NeedsAnUnsetVariable),
            "env var not a number": lambda: self._container.get(NeedsANumber),
            "scoped service from the root": lambda: self._container.get(UnitOfWork),
            "removed service": lambda: self._container.get(SmsNotifier),
            "unknown parameter": _sync(lambda: self._container.get_parameter("shop.nope")),
            "lazy parameter read raw": _sync(lambda: self._parameters.get("shop.name")),
            "unknown locator key": lambda: self._exporters.export("pdf", []),
            # ---- dependency injection: while building --------------------------------
            "environment not allowed": _sync(lambda: kernel.with_env("staging").build()),
            "unregistered dependency": _sync(
                lambda: Kernel("bookshop.diagnostics.broken_app", env="test", bundles={}).build()
            ),
            "two base configs": _sync(
                lambda: Kernel(
                    "bookshop.diagnostics.broken_config",
                    env="test",
                    bundles={ClockBundle: {"all": True}},
                ).build()
            ),
            # ---- messenger -----------------------------------------------------------
            "handler with a bad signature": _sync(_declare_bad_handler),
            "unknown transport": _sync(lambda: self._workers.worker(["nope"])),
            "DSN without a scheme": _sync(lambda: TransportConfig("no-scheme-here").parsed),
            "pydantic message rules": _sync(lambda: ReindexCatalog(reason="x")),
            "handler failing in a worker": self._rejected_by_worker,
            # ---- logging, clock, dotenv, console -------------------------------------
            "unknown level": _sync(lambda: Level.parse("loud")),
            "unknown channel": _sync(lambda: self._factory.logger("nope")),
            "bad clock modifier": _sync(lambda: now("+1 dya")),
            "unknown timezone": _sync(lambda: resolve_timezone("Mars/Olympus_Mons")),
            "dotenv line without =": _sync(lambda: Dotenv(environ={}).parse("NOT A BINDING")),
            "dotenv reference loop": _sync(lambda: Dotenv(environ={}).parse("A=${B}\nB=${A}")),
            "dotenv file missing": _sync(lambda: Dotenv(environ={}).load("/nonexistent/.env")),
            "question default not a choice": _sync(lambda: io.ask("Pick?", "z", choices=["a"])),
            "command name claimed twice": _sync(_declare_twice),
        }

    async def _rejected_by_worker(self) -> str:
        """Queue a receipt whose handler raises; the worker rejects it and carries on."""
        _ = await self._bus.dispatch(SendReceipt(uuid4(), "reader@mail.invalid", Decimal(1)))
        await self._workers.worker(["jobs"]).run()
        jobs = self._transports.create({"jobs": self._config.transports["jobs"]})["jobs"]
        if not isinstance(jobs, InMemoryTransport) or not jobs.rejected:
            return "nothing was rejected"
        details = jobs.rejected[-1].last(ErrorDetailsStamp)
        reason = f"{details.exception_class}: {details.exception_message}" if details else "?"
        return f"rejected, not raised — ErrorDetailsStamp says {reason}"


def _sync(call: Callable[[], object]) -> Case:
    """Wrap a synchronous case so every case is awaited the same way."""

    async def run() -> object:
        return call()

    return run


def _declare_bad_handler() -> object:
    """A handler whose second parameter is neither an ``Envelope`` nor container-provided."""

    async def bad(message: AuditEvent, extra: str) -> None:
        del message, extra

    return as_message_handler(AuditEvent, HandlersLocator())(bad)


def _declare_twice() -> object:
    """Declare two commands under one name, in a private locator — not the process's."""
    commands = CommandsLocator()

    def first(io: ConsoleStyle) -> int:
        del io
        return 0

    def second(io: ConsoleStyle) -> int:
        del io
        return 0

    _ = as_command("twice", registry=commands)(first)
    return as_command("twice", registry=commands)(second)
