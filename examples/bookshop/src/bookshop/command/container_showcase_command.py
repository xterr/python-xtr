"""``di:show`` — what the container decided: removals, decorations, orders, parameters."""

from __future__ import annotations

from typing import Annotated, Literal, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import ContainerBagInterface, KernelInterface, Target
from xtr_dependency_injection.exception import EnvPlaceholderError
from xtr_service_contracts import ContainerInterface

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.compilation_summary import CompilationSummary
from bookshop.service.export_registry import ExportRegistry
from bookshop.service.fraud_check_interface import FraudCheckInterface
from bookshop.service.in_memory_book_catalog import InMemoryBookCatalog
from bookshop.service.limit_fraud_check import LimitFraudCheck
from bookshop.service.log_notifier import LogNotifier
from bookshop.service.notifier_interface import NotifierInterface
from bookshop.service.payment_gateway_interface import PaymentGatewayInterface
from bookshop.service.price_calculator import PriceCalculator
from bookshop.service.redis_catalog_warmer import RedisCatalogWarmer
from bookshop.service.refund_service import RefundService
from bookshop.service.security_audit_trail import SecurityAuditTrail
from bookshop.service.sms_notifier import SmsNotifier
from bookshop.service.smtp_notifier import SmtpNotifier

__all__ = ["ContainerShowcaseCommand"]


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
