"""Development commands — scanned only where ``DevToolsBundle`` is active (dev, test).

- ``bundle:check`` — the zero-config contract, for every bundle the application uses.
- ``demo:frozen-clock`` — ``boot_for_test`` with an override, and the clock's test helpers.
- ``demo:wireup`` — the bundle pipeline without a kernel, and a kernel with its own environ.
- ``demo:dotenv`` — the dotenv loader's API, on a sandboxed mapping.
- ``demo:without-container`` — every library used directly, no kernel at all.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, final

import wireup
from xtr_clock import (
    Clock,
    ClockAwareMixin,
    ClockInterface,
    DatePoint,
    MockClock,
    MonotonicClock,
    SystemClock,
    apply_modifier,
    local_timezone,
    now,
)
from xtr_clock.bundle import ClockBundle
from xtr_clock.testing import mock_time
from xtr_console import (
    Application,
    ApplicationTester,
    CommandsLocator,
    CommandTester,
    ConsoleStyle,
    ExitCode,
    as_command,
    escape,
)
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.integration.wireup import (
    create_container,
    engine_container,
    injectables,
)
from xtr_dependency_injection.testing import assert_zero_config, boot_for_test
from xtr_dotenv import PATH_VAR, TRACKING_VAR, Dotenv
from xtr_dotenv.bundle import DotenvBundle
from xtr_logging import (
    Logger,
    LoggerFactory,
    LoggingConfig,
    LogRecord,
    PlaceholderProcessor,
    ProcessorRegistry,
    Services,
    TestHandler,
    as_processor,
    bound_context,
)
from xtr_logging.bundle import LoggingBundle
from xtr_logging_contracts import Level, LoggerAware, NullLogger
from xtr_messenger import (
    HandlersLocator,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
    as_message_handler,
)
from xtr_messenger.bundle import MessengerBundle

from bookshop.kernel import EXCLUDE, PROJECT_DIR, kernel
from bookshop.messaging.messages import AuditEvent
from fulltext import SearchEngineInterface
from fulltext.bundle import FulltextBundle, FulltextConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import Bundle

__all__ = [
    "BundleCheckCommand",
    "dotenv_api",
    "frozen_clock",
    "wireup_integration",
    "without_container",
]

_BUNDLES: tuple[type[Bundle[Any]], ...] = (  # pyright: ignore[reportExplicitAny] — any config.
    ClockBundle,
    LoggingBundle,
    ConsoleBundle,
    MessengerBundle,
    DotenvBundle,
    FulltextBundle,
)


@final
@as_command("bundle:check")
class BundleCheckCommand:
    """Check every bundle builds, boots and shuts down with no configuration at all.

    A bundle can arrive transitively — required by another — so it must work unconfigured.
    ``assert_zero_config`` builds a kernel of the bundle and its requirements alone.
    """

    async def __call__(self, io: ConsoleStyle) -> int:
        """Check each bundle.

        Args:
            io: Where the command writes.
        """
        failures = 0
        for bundle in io.progress(_BUNDLES, description="Checking"):
            try:
                await assert_zero_config(bundle)
            except Exception as error:  # noqa: BLE001 — reported, then the next bundle runs.
                failures += 1
                io.error(f"{bundle.metadata().name}: {escape(repr(error))}")
            else:
                io.text(f"[green]✔[/green] {bundle.metadata().name}")
        return ExitCode.FAILURE if failures else ExitCode.SUCCESS


@as_command("demo:frozen-clock")
async def frozen_clock(io: ConsoleStyle) -> int:
    """Boot a second, test kernel with the clock replaced, and use the clock's test helpers.

    Args:
        io: Where the command writes.
    """
    frozen = Clock(MockClock("2030-01-01 09:00:00", "UTC"), "UTC")
    rows: list[list[str]] = []
    # boot_for_test builds for "test" and applies overrides before any boot hook runs;
    # the clock bundle then installs the override as the clock in force.
    async with await boot_for_test(kernel, overrides={Clock: frozen}) as booted:
        injected = await booted.container.get(ClockInterface)
        rows.append(["test kernel: injected clock", injected.now().isoformat()])
        rows.append(["test kernel: xtr_clock.now()", now().isoformat()])
        frozen.sleep(3600)
        rows.append(["after clock.sleep(3600)", now().isoformat()])
    rows.append(["back in this kernel: now()", now().isoformat()[:19]])
    with mock_time("2024-02-29 12:00:00") as clock:
        rows.append(["mock_time: now()", now().isoformat()])
        rows.append(['now("+1 year")', now("+1 year").isoformat()])
        rows.append(
            [
                'modify("+1 month") then "noon"',
                clock.now().modify("+1 month").modify("noon").isoformat(),
            ]
        )
        rows.append(
            [
                'DatePoint.parse("tomorrow Asia/Tokyo")',
                DatePoint.parse("tomorrow Asia/Tokyo").isoformat(),
            ]
        )
        rows.append(
            [
                'with_timezone("America/New_York")',
                clock.now().with_timezone("America/New_York").isoformat(),
            ]
        )
        rows.append(
            [
                'apply_modifier(dt, "-2 hours 30 minutes")',
                apply_modifier(clock.now(), "-2 hours 30 minutes").isoformat(),
            ]
        )
        await clock.sleep_async(86400)
        rows.append(["after sleep_async(86400)", now().isoformat()])
        audit = _AuditLog()
        rows.append(["ClockAwareMixin, unset", audit.stamp()])
        audit.set_clock(MockClock("1999-12-31 23:59:59"))
        rows.append(["ClockAwareMixin, set_clock()", audit.stamp()])
    monotonic = MonotonicClock()
    rows.append(["MonotonicClock", monotonic.now().isoformat()[:19]])
    rows.append(
        [
            "SystemClock in Europe/Paris",
            SystemClock().with_timezone("Europe/Paris").now().isoformat()[:19],
        ]
    )
    rows.append(
        [
            "DatePoint.from_datetime",
            DatePoint.from_datetime(datetime(2020, 1, 1, tzinfo=UTC)).isoformat(),
        ]
    )
    rows.append(["local_timezone()", str(local_timezone())])
    io.table(["What", "Instant"], rows)
    return ExitCode.SUCCESS


class _AuditLog(ClockAwareMixin):
    """A class that cannot take its clock in the constructor."""

    def stamp(self) -> str:
        return self.now().isoformat()


@as_command("demo:wireup")
async def wireup_integration(io: ConsoleStyle) -> int:
    """The bundle pipeline without a kernel — for a plain wireup application.

    Args:
        io: Where the command writes.
    """
    rows: list[list[str]] = []
    # create_container: bundles, configs, parameters and an environ of its own.
    container = create_container(
        [FulltextBundle],
        configs=[FulltextConfig(pipeline=("lowercase", "words"), max_results=3)],
        parameters={"standalone": {"purpose": "demo"}},
        environ={"APP_TIMEZONE": "UTC"},
    )
    engine = await container.get(SearchEngineInterface)
    engine.index("b1", "Standalone search with wireup")
    rows.append(["create_container([FulltextBundle])", str(engine.search("wireup"))])
    await container.close()
    # injectables: the same pipeline, handed to wireup.create_async_container. A bundle
    # setting parameters is refused here (the fulltext bundle does), the clock's is not.
    plain = wireup.create_async_container(injectables=injectables([ClockBundle]))
    clock = await plain.get(ClockInterface)
    rows.append(["injectables([ClockBundle])", type(clock).__name__])
    await plain.close()
    # Kernel(environ=...): a kernel reading APP_ENV, APP_DEBUG and every env() from its own
    # mapping instead of os.environ — what a test gives each kernel.
    isolated = Kernel("bookshop", exclude=EXCLUDE, environ={"APP_ENV": "test", "APP_DEBUG": "0"})
    rows.append(["Kernel(environ=...).environment", isolated.environment])
    rows.append(["Kernel(environ=...).debug", str(isolated.debug)])
    # engine_container: the wireup container behind a compiled kernel, for integrations
    # such as wireup.integration.fastapi.setup(engine_container(compiled), app).
    compiled = isolated.build()
    rows.append(["engine_container(compiled)", type(engine_container(compiled)).__name__])
    io.table(["Call", "Result"], [[a, escape(b)] for a, b in rows])
    return ExitCode.SUCCESS


@as_command("demo:dotenv")
async def dotenv_api(io: ConsoleStyle) -> int:
    """The dotenv loader on a sandboxed mapping: nothing here touches ``os.environ``.

    Args:
        io: Where the command writes.
    """
    rows: list[list[str]] = []
    base = PROJECT_DIR / "resources" / "dotenv-demo" / ".env"
    # load_env: .env is missing there, so .env.dist is read instead; then .env.prod.
    sandbox: dict[str, str] = {"APP_ENV": "prod"}
    _ = Dotenv(environ=sandbox).load_env(str(base), default_env="dev")
    rows.append(["load_env (from .env.dist)", _pick(sandbox, "SOURCE", "GREETING")])
    rows.append([TRACKING_VAR, sandbox.get(TRACKING_VAR, "")])
    rows.append([PATH_VAR, sandbox.get(PATH_VAR, "")[-40:]])
    # parse: one file's text, expanded, returned — nothing written.
    parsed = Dotenv(environ={}).parse("A=1\nB=${A}-${MISSING:-fallback}\nC='$A literal'\n")
    rows.append(["parse()", repr(parsed)])
    # populate: write values under the tracking rules — a real variable is never replaced.
    real = {"KEEP": "real"}
    _ = Dotenv(environ=real).populate({"KEEP": "from file", "NEW": "added"})
    rows.append(["populate() keeps real vars", repr({k: real[k] for k in ("KEEP", "NEW")})])
    _ = Dotenv(environ=real).populate({"KEEP": "forced"}, override_existing_vars=True)
    rows.append(["populate(override_existing_vars=True)", real["KEEP"]])
    # load / overload: explicit files, without and with overriding real variables.
    loaded: dict[str, str] = {"SOURCE": "real"}
    _ = Dotenv(environ=loaded).load(str(base) + ".dist")
    rows.append(["load() — the real SOURCE wins", loaded["SOURCE"]])
    _ = Dotenv(environ=loaded).overload(str(base) + ".dist")
    rows.append(["overload() — the file wins", loaded["SOURCE"]])
    # boot_env: the cascade, then APP_DEBUG set from the environment kind.
    booted: dict[str, str] = {"APP_ENV": "prod"}
    _ = Dotenv(environ=booted).set_prod_envs(("prod",)).boot_env(str(base))
    rows.append(["boot_env() in prod -> APP_DEBUG", booted["APP_DEBUG"]])
    io.table(["Call", "Result"], [[a, escape(b)] for a, b in rows])
    return ExitCode.SUCCESS


def _pick(values: dict[str, str], *names: str) -> str:
    return ", ".join(f"{name}={values.get(name)}" for name in names)


@as_command("demo:without-container")
async def without_container(io: ConsoleStyle) -> int:
    """Every library, used directly: the bundles are an integration, never a requirement.

    Args:
        io: Where the command writes.
    """
    rows: list[list[str]] = []
    # Logging: a logger, a handler, a processor — and a function processor declared into a
    # private registry with @as_processor(registry=...).
    registry = ProcessorRegistry()

    @as_processor(channel="app", registry=registry)
    def add_origin(record: LogRecord) -> LogRecord:
        return record.with_extra({"origin": "without-container"})

    handler = TestHandler()
    logger = Logger("app", [handler], [PlaceholderProcessor()], clock=MockClock("2026-01-01"))
    with bound_context({"request_id": "r-1"}):
        logger.info("hello {who}", {"who": "world"})
    rows.append(["Logger + TestHandler", handler.formatted[0].strip()[:80]])
    config = LoggingConfig.from_mapping(
        tomllib.loads('channels = ["audit"]\n[handlers.mem]\ntype = "service"\nid = "mem"\n')
    )
    memory = TestHandler()
    with LoggerFactory(
        config, services=Services(handlers={"mem": memory}), registry=registry
    ) as factory:
        factory.logger("audit").warning("from TOML config")
    rows.append(
        ["LoggerFactory from TOML", f"{memory.records[0].channel}: {memory.records[0].extra}"]
    )
    rows.append(["Level.parse(3) — an RFC 5424 severity", Level.parse(3).name])
    aware = _Aware()
    rows.append(["LoggerAware default", type(aware.logger).__name__])
    # Messenger: a bus over a private handlers locator.
    handled: list[str] = []
    handlers = HandlersLocator()

    @as_message_handler(AuditEvent, handlers)
    async def on_audit(message: AuditEvent) -> None:
        handled.append(message.subject)

    bus_config = MessageBusConfig(
        transports={"sync": TransportConfig("sync://")}, routing={AuditEvent: "sync"}
    )
    bus = MessageBusFactory(bus_config, handlers=handlers, logger=NullLogger()).bus()
    _ = await bus.dispatch(AuditEvent("standalone", "no kernel"))
    rows.append(["MessageBusFactory + sync://", ", ".join(handled)])
    # Console: an application over a private commands locator, driven by a tester.
    commands = CommandsLocator()

    @as_command("hello", registry=commands)
    async def hello(io: ConsoleStyle, name: str = "world") -> int:
        io.text(f"hello {name}")
        return ExitCode.SUCCESS

    application = Application("mini", "0.1", commands=commands, catch_exceptions=False)
    tester = CommandTester(application, "hello")
    code = await tester.execute(["ada"])
    rows.append(["CommandTester('hello', ['ada'])", f"{code}: {tester.display.strip()}"])
    whole = ApplicationTester(application)
    _ = await whole.execute(["--version"])
    rows.append(["ApplicationTester(['--version'])", whole.display.strip()])
    del hello, on_audit, add_origin
    io.table(["Library use", "Result"], [[a, escape(b)] for a, b in rows])
    return ExitCode.SUCCESS


class _Aware(LoggerAware):
    """A class that logs through ``self.logger``: a ``NullLogger`` until ``set_logger``."""
