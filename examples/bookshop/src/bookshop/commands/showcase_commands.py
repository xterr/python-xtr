"""``env:show``, ``di:show``, ``cache:clear``, ``logs:recent`` — what the container decided."""

from __future__ import annotations

import os
from typing import Annotated, Literal, cast, final

from xtr_console import ConsoleStyle, ExitCode, Verbosity, as_command, escape
from xtr_dependency_injection import (
    ContainerBagInterface,
    Injected,
    KernelInterface,
    ServicesResetter,
    Target,
)
from xtr_dependency_injection.exception import EnvPlaceholderError
from xtr_dotenv import PATH_VAR, TRACKING_VAR
from xtr_logging import LoggerFactory, TestHandler
from xtr_service_contracts import ContainerInterface

from bookshop.catalog import BookCatalogInterface
from bookshop.catalog.in_memory_book_catalog import InMemoryBookCatalog
from bookshop.catalog.redis_catalog_warmer import RedisCatalogWarmer
from bookshop.compiler_passes import CompilationSummary
from bookshop.env.env_showcase import EnvShowcase
from bookshop.notifications import NotifierInterface
from bookshop.notifications.notifiers import LogNotifier, SmsNotifier, SmtpNotifier
from bookshop.observability.security_audit_trail import SecurityAuditTrail
from bookshop.payments import FraudCheckInterface, PaymentGatewayInterface
from bookshop.payments.fraud_check import LimitFraudCheck
from bookshop.payments.payment_gateway import RefundService
from bookshop.pricing import PriceCalculator
from bookshop.reporting import ExportRegistry
from bookshop.settings import ShopSettings
from fulltext import QueryLog, SearchEngineInterface

__all__ = ["ContainerShowcaseCommand", "clear_caches", "recent_logs", "show_environment"]

_ECOSYSTEM_VARIABLES = ("APP_ENV", "APP_DEBUG", "SHELL_VERBOSITY", TRACKING_VAR, PATH_VAR)


@as_command("env:show")
async def show_environment(
    io: ConsoleStyle,
    showcase: Injected[EnvShowcase],
    settings: Injected[ShopSettings],
    kernel: Injected[KernelInterface],
) -> int:
    """Show every environment variable processor's result, and the typed settings.

    Args:
        io: Where the command writes.
        showcase: One value per env processor.
        settings: The same cascade, as a pydantic-settings model.
        kernel: The kernel's environment and debug flag.
    """
    io.title(f"Environment: {kernel.environment} (debug={kernel.debug})")
    io.section("Variables the xtr packages read or write")
    io.table(
        ["Variable", "Value"],
        [[name, escape(os.environ.get(name, "(unset)"))[:80]] for name in _ECOSYSTEM_VARIABLES],
    )
    io.section("Autowire(env=...) — one per processor")
    io.table(
        ["Processor", "Expression", "Value"],
        [
            [label, expression, escape(repr(value))[:70]]
            for label, (expression, value) in showcase.values.items()
        ],
    )
    io.section("DotenvSettings — the same cascade, typed")
    io.table(
        ["Field", "Value"],
        [[k, repr(v)] for k, v in cast("dict[str, object]", settings.model_dump()).items()],
    )
    return ExitCode.SUCCESS


@final
@as_command("di:show")
class ContainerShowcaseCommand:
    """Show what the container decided: removals, decorations, orders, parameters.

    A class command: its constructor is injected like any service's, a qualified one
    included (``Target``).
    """

    def __init__(  # noqa: PLR0913, PLR0917 — one parameter per thing it reports on.
        self,
        container: ContainerInterface,
        kernel: KernelInterface,
        parameters: ContainerBagInterface,
        summary: CompilationSummary,
        calculator: PriceCalculator,
        fraud: FraudCheckInterface,
        ops: Annotated[NotifierInterface, Target("ops")],
        exporters: ExportRegistry,
    ) -> None:
        """Keep what it reports on."""
        self._container = container
        self._kernel = kernel
        self._parameters = parameters
        self._summary = summary
        self._calculator = calculator
        self._fraud = fraud
        self._ops = ops
        self._exporters = exporters

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        report: Literal["bundles", "configs", "definitions", "scan"] | None = None,
    ) -> int:
        """Show the container's decisions.

        Args:
            io: Where the command writes.
            report: Also print one section of the kernel's report (``scan`` lists every
                module scanned and every object ``@when`` left out).
        """
        io.title(f"{self._kernel.name} — {self._kernel.environment}")
        self._kernel_info(io)
        self._conditional(io)
        self._decorations(io)
        self._parameters_section(io)
        io.section("Compilation")
        io.text(
            f"{self._summary.definitions} definitions, {self._summary.aliases} aliases; "
            f"compiler log ({len(self._summary.log)} lines) with -v"
        )
        if io.is_verbose():
            io.listing([escape(line) for line in self._summary.log])
        if report is not None:
            io.section(f"Report: {report}")
            io.text(escape(self._kernel.report.render(report)))
        return ExitCode.SUCCESS

    def _kernel_info(self, io: ConsoleStyle) -> None:
        io.section("Kernel")
        io.table(
            ["", ""],
            [
                ["name", self._kernel.name],
                ["environment", self._kernel.environment],
                ["debug", str(self._kernel.debug)],
                ["project_dir", str(self._kernel.project_dir)],
                ["bundles", ", ".join(self._kernel.bundles)],
            ],
        )

    def _conditional(self, io: ConsoleStyle) -> None:
        io.section("What exists here — container.has(...)")
        checks: list[tuple[str, type, str | None, str]] = [
            ("PaymentGatewayInterface", PaymentGatewayInterface, None, '@when("prod")'),
            ("RefundService", RefundService, None, "remove_if_missing(service=gateway)"),
            ("RedisCatalogWarmer", RedisCatalogWarmer, None, 'remove_if_missing(package="redis")'),
            ("SmsNotifier", SmsNotifier, None, "remove_if_missing(class_=twilio…)"),
            ("SecurityAuditTrail", SecurityAuditTrail, None, "remove_if_missing x2, both hold"),
            ("LogNotifier", LogNotifier, None, '@when_not("prod")'),
            ("SmtpNotifier", SmtpNotifier, None, '@when("prod")'),
            ("NotifierInterface", NotifierInterface, None, "@as_alias of either"),
            ('NotifierInterface["ops"]', NotifierInterface, "ops", "qualified factory"),
            ("InMemoryBookCatalog", InMemoryBookCatalog, None, "built by a factory, not keyed"),
        ]
        io.table(
            ["Service", "Exists", "Why"],
            [
                [name, "yes" if self._container.has(key, qualifier) else "no", why]
                for name, key, qualifier, why in checks
            ],
        )

    def _decorations(self, io: ConsoleStyle) -> None:
        io.section("Decorations, collections, OnInvalid")
        catalog_report = next(
            d for d in self._kernel.report.definitions if d.key == (BookCatalogInterface, None)
        )
        io.table(
            ["What", "Result"],
            [
                ["BookCatalogInterface decorated by", " <- ".join(catalog_report.decorated_by)],
                ["Sequence[PricingRule] order", " -> ".join(map(str, self._calculator.indexes()))],
                [
                    "NotifierInterface['ops']",
                    type(self._ops).__name__ + " (as_decorator qualifier)",
                ],
                [
                    "FraudCheckInterface",
                    (
                        f"{type(self._fraud).__name__}, wraps a scorer: "
                        f"{isinstance(self._fraud, LimitFraudCheck) and self._fraud.wraps_a_scorer}"
                        " (OnInvalid.NULL)"
                    ),
                ],
                ["ServiceLocator formats", ", ".join(self._exporters.formats())],
            ],
        )

    def _parameters_section(self, io: ConsoleStyle) -> None:
        io.section("Parameters — ContainerInterface and ContainerBagInterface")
        bag = self._parameters
        try:
            raw_name: object = bag.get("shop.name")
        except EnvPlaceholderError as error:
            raw_name = f"EnvPlaceholderError: {error}"
        io.table(
            ["Call", "Result"],
            [
                [
                    'container.get_parameter("shop.currency")',
                    str(self._container.get_parameter("shop.currency")),
                ],
                [
                    'container.has_parameter("shop.nope")',
                    str(self._container.has_parameter("shop.nope")),
                ],
                ['bag.get("shop.log_dir")', str(bag.get("shop.log_dir"))],
                ['bag.get("shop.motto")', str(bag.get("shop.motto"))],
                ['bag.get("shop.name") — holds env()', escape(str(raw_name))],
                [
                    'bag.resolve_value("%shop.currency% only")',
                    str(bag.resolve_value("%shop.currency% only")),
                ],
                ['bag.escape_value("50%")', str(bag.escape_value("50%"))],
                ['bag.unescape_value("50%%")', str(bag.unescape_value("50%%"))],
                ["bag.all() keys", ", ".join(sorted(bag.all()))],
            ],
        )


@as_command("cache:clear")
async def clear_caches(
    io: ConsoleStyle,
    resetter: Injected[ServicesResetter],
    engine: Injected[SearchEngineInterface],
    queries: Injected[QueryLog],
) -> int:
    """Reset every resettable service that was built — what a worker does between messages.

    ``ServicesResetter`` calls ``reset`` on every built service implementing
    ``ResetInterface`` (the catalog cache, the logger factory) and the method named by every
    explicit ``kernel.reset`` tag (the query log's ``clear``). Services never built are not
    touched.

    Args:
        io: Where the command writes.
        resetter: The kernel's resetter.
        engine: The search engine, queried so the query log holds something.
        queries: The query log, to show the effect.
    """
    _ = engine.search("pragmatic")
    _ = engine.search("history")
    before = len(queries.queries())
    await resetter.reset()
    io.table(
        ["", "Before", "After"], [["logged queries", str(before), str(len(queries.queries()))]]
    )
    io.success("Every built resettable service was reset.")
    return ExitCode.SUCCESS


@as_command("logs:recent")
async def recent_logs(
    io: ConsoleStyle,
    factory: Injected[LoggerFactory],
    *,
    count: int = 10,
) -> int:
    """Print the last records the in-memory handler kept.

    Args:
        io: Where the command writes.
        factory: The logger factory — any configured handler is reachable by name.
        count: How many records.
    """
    handler = factory.handler("memory")
    if not isinstance(handler, TestHandler):
        io.error("The memory handler is not a TestHandler.")
        return ExitCode.FAILURE
    io.text(f"channels: {', '.join(factory.channels)}", verbosity=Verbosity.VERBOSE)
    io.table(
        ["Channel", "Level", "Message"],
        [
            [record.channel, record.level.name, escape(record.message)]
            for record in handler.records[-count:]
        ],
    )
    return ExitCode.SUCCESS
