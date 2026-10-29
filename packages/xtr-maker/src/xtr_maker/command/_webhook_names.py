"""One webhook type, every name ``make:webhook`` spells it with, and what its templates read."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, final

from xtr_maker.class_name import ClassName
from xtr_maker.import_collector import ImportCollector
from xtr_maker.name_converter import NameConverter

from ._request_matchers import request_matcher_body

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_maker.generator import Generator

    from ._request_matchers import RequestMatcherChoice

__all__ = ["WebhookNames"]


@final
@dataclass(frozen=True, slots=True)
class WebhookNames:
    """A webhook type, and the classes, module, function and variable named after it.

    Attributes:
        type: The type as typed: the URL segment, and the events' source name.
        parser: The request parser class.
        consumer: The remote event consumer class.
    """

    type: str
    parser: ClassName
    consumer: ClassName

    @classmethod
    def create(cls, webhook: str, *, root_package: str) -> WebhookNames:
        """Name the classes of ``webhook``: ``acme-pay`` → ``AcmePayRequestParser``, ….

        Raises:
            InvalidClassNameError: When the type spells no class name.
        """
        base = NameConverter.as_class_name(webhook)

        def named(kind: str, suffix: str) -> ClassName:
            return ClassName.create(base, root_package=root_package, kind=kind, suffix=suffix)

        return cls(
            webhook, named("webhook", "RequestParser"), named("remote_event", "WebhookConsumer")
        )

    @property
    def snake_name(self) -> str:
        """The type in snake case: ``acme-pay`` → ``acme_pay``."""
        return NameConverter.as_snake_case(self.parser.name_without_suffix)

    @property
    def secret(self) -> str:
        """The environment variable holding the secret: ``ACME_PAY_WEBHOOK_SECRET``."""
        return f"{self.snake_name.upper()}_WEBHOOK_SECRET"

    @property
    def transform(self) -> str:
        """The configuration transform adding the route: ``webhook_acme_pay``."""
        return f"webhook_{self.snake_name}"

    @property
    def transform_path(self) -> PurePosixPath:
        """The transform's module, relative to the application package's directory."""
        return PurePosixPath("config", "packages", f"{self.transform}.py")

    def parser_context(
        self, matchers: Sequence[RequestMatcherChoice], generator: Generator
    ) -> dict[str, object]:
        """Return what the parser template reads: its imports, its matcher and its header."""
        imports = ImportCollector(self.parser.root_package)
        _ = imports.add("hmac", "compare_digest")
        _ = imports.add("typing", "Final")
        if generator.final_classes:
            _ = imports.add("typing", "final")
        _ = imports.add("typing_extensions", "override")
        _ = imports.add("xtr_remote_event", "RemoteEvent")
        _ = imports.add("xtr_webhook.client", "AbstractRequestParser")
        _ = imports.add("xtr_webhook.exception", "RejectWebhookError")
        _ = imports.add("collections.abc", "Sequence", type_checking=True)
        _ = imports.add("xtr_http_foundation", "RequestMatcherInterface", type_checking=True)
        _ = imports.add("xtr_http_message_contracts", "ServerRequestInterface", type_checking=True)
        body = request_matcher_body(matchers, imports)
        words = NameConverter.words(self.parser.name_without_suffix)
        header = "-".join((*(word.capitalize() for word in words), "Signature"))
        return {
            **self._names(),
            "imports": imports.render(),
            "request_matcher": body,
            "signature_header": _literal(header),
        }

    def consumer_context(self, generator: Generator) -> dict[str, object]:
        """Return what the consumer template reads: its imports and the type."""
        imports = ImportCollector(self.consumer.root_package)
        if generator.final_classes:
            _ = imports.add("typing", "final")
        _ = imports.add("xtr_remote_event", "as_remote_event_consumer")
        _ = imports.add("xtr_remote_event", "RemoteEvent", type_checking=True)
        return {**self._names(), "imports": imports.render()}

    def transform_context(self) -> dict[str, object]:
        """Return what the route's transform reads: its imports, its name and the secret's."""
        imports = ImportCollector(self.parser.root_package)
        _ = imports.add("dataclasses", "replace")
        _ = imports.add("xtr_dependency_injection", "configure")
        _ = imports.add("xtr_dependency_injection", "env")
        _ = imports.add("xtr_webhook.bundle", "RouteConfig")
        _ = imports.add("xtr_webhook.bundle", "WebhookConfig")
        parser_class = imports.add(self.parser.module, self.parser.short_name)
        return {
            **self._names(),
            "imports": imports.render(),
            "function_name": self.transform,
            "parser_class": parser_class,
            "env_name": self.secret,
            "env_literal": _literal(self.secret),
        }

    def _names(self) -> dict[str, object]:
        return {"name": self.type, "name_literal": _literal(self.type)}


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)
