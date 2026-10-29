"""``make:webhook``: a parser for one sender's webhooks, its consumer, and the route between."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import Autowire, Injected

from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.

from ._request_matchers import pick_request_matchers
from ._webhook_names import WebhookNames

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ROUTED_TYPES_PARAMETER", "MakeWebhookCommand"]

ROUTED_TYPES_PARAMETER: Final = "maker.webhook.routed_types"
"""The parameter holding the webhook types the application routes, which the bundle sets.

The types are read from the webhook configuration as the kernel builds, not
from the configuration injected: injecting it resolves every route's secret,
and a secret not set yet must not stop a webhook from being made.
"""

_TYPE: Final = re.compile(r"[A-Za-z_.\-][A-Za-z0-9_.\-]*")
"""What a webhook type may be: the segment of the URL its sender posts to."""

_ATTEMPTS: Final = 3
"""How many times the type is asked: an input that has ended answers empty every time."""

_PARSER_TEMPLATE: Final = "webhook/request_parser.py.jinja"
_CONSUMER_TEMPLATE: Final = "webhook/webhook_consumer.py.jinja"
_TRANSFORM_TEMPLATE: Final = "webhook/webhook_config.py.jinja"


@final
@as_command(
    "make:webhook",
    description="Write a parser for one sender's webhooks, its consumer, and the route between.",
)
class MakeWebhookCommand:
    """Writes the parser, the consumer and the route of one webhook type.

    The type is the segment of the URL the sender posts to, and the name the
    events it carries are consumed under. Three modules come out of it:
    ``webhook/<type>_request_parser.py``, which claims the sender's requests
    with the matchers picked, compares a header with the secret and reads the
    event; ``remote_event/<type>_webhook_consumer.py``, which receives that
    event; and ``config/packages/webhook_<type>.py``, a configuration
    transform adding the route — so the application's own webhook
    configuration is never edited, and its secret stays an environment
    placeholder.

    The matchers are asked for one at a time whether or not the type was
    given. Without a terminal (``-n``) they come from ``--matcher``, else the
    method and JSON ones; the type must be given.
    """

    __slots__ = ("_file_manager", "_routed")

    def __init__(
        self,
        file_manager: FileManager,
        routed_types: Annotated[list[str], Autowire(param=ROUTED_TYPES_PARAMETER)],
    ) -> None:
        """Write into the package ``file_manager`` holds, beside the routes already configured.

        Args:
            file_manager: The application package the modules are written into.
            routed_types: The webhook types the configuration routes; each is refused.
        """
        self._file_manager = file_manager
        self._routed = frozenset(routed_types)

    async def __call__(
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        *,
        matcher: list[str] | None = None,
    ) -> int:
        """Write a webhook's parser, consumer and route.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the files, all or none.
            name: The webhook type, such as ``stripe``: the segment of the URL
                the sender posts to.
            matcher: A request matcher the parser claims requests with, by its
                class name without ``RequestMatcher`` (``Method``, ``IsJson``);
                repeat it for several.
        """
        try:
            webhook = WebhookNames.create(
                self._webhook_type(io, name), root_package=self._file_manager.root_package
            )
            matchers = pick_request_matchers(io, matcher)
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        try:
            parser_path = generator.generate_class(
                webhook.parser, _PARSER_TEMPLATE, webhook.parser_context(matchers, generator)
            )
            consumer_path = generator.generate_class(
                webhook.consumer, _CONSUMER_TEMPLATE, webhook.consumer_context(generator)
            )
            _ = generator.generate_file(
                self._file_manager.package_dir / webhook.transform_path,
                _TRANSFORM_TEMPLATE,
                webhook.transform_context(),
            )
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(
            f"Wrote {webhook.parser.short_name}, {webhook.consumer.short_name}"
            f" and the {escape(webhook.type)} route."
        )
        self._next_steps(io, webhook, (parser_path, consumer_path))
        return ExitCode.SUCCESS

    def _webhook_type(self, io: ConsoleStyle, typed: str | None) -> str:
        """Return the type ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no type was given and nothing may be
                asked, or the type is not one, or is already routed — after
                the last attempt, when asked.
        """
        if typed is not None:
            return self._checked_type(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the webhook type to write: make:webhook <name>, such as make:webhook stripe."
            )
        question = "The webhook type, the last segment of its URL (such as [cyan]stripe[/])"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._checked_type(io.ask(question))
            except InvalidArgumentError as error:
                io.error(escape(str(error)))
        return self._checked_type(io.ask(question))

    def _checked_type(self, typed: str) -> str:
        webhook = typed.strip()
        if _TYPE.fullmatch(webhook) is None:
            raise InvalidArgumentError(
                f"{webhook!r} cannot name a webhook type: start with a letter, '_', '.' or '-',"
                " then use letters, digits, '_', '.' or '-'."
            )
        if webhook in self._routed:
            raise InvalidArgumentError(f"The webhook type {webhook!r} is already routed.")
        return webhook

    def _next_steps(
        self, io: ConsoleStyle, webhook: WebhookNames, written: tuple[Path, Path]
    ) -> None:
        parser_path, consumer_path = (escape(self._file_manager.relative(path)) for path in written)
        typed = escape(webhook.type)
        io.text("Next:")
        io.text(f"  - Add {webhook.secret} to .env.local: the secret {typed} shares with you.")
        io.text(
            f"  - Open {parser_path} and replace the secret check"
            " with the one its sender's protocol asks for."
        )
        io.text(f"  - Open {consumer_path} and write what an event leads to.")
        resource = escape('resources["webhook"]')
        io.text(
            "  - Make sure config/routes/webhook.py exists, with an @as_routes function including"
            f" {resource}: the sender posts to /webhook/{typed}."
        )
