"""The request matchers ``make:webhook`` offers, how they are picked, and the code it writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from xtr_console import escape

from xtr_maker.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_console import ConsoleStyle

    from xtr_maker.import_collector import ImportCollector

__all__ = [
    "REQUEST_MATCHERS",
    "RequestMatcherChoice",
    "pick_request_matchers",
    "request_matcher_body",
]

_MODULE: Final = "xtr_http_foundation"
"""Where every matcher, the chain included, is exported from."""

_BODY: Final = " " * 8
"""The indent of a method's body: the statement written goes inside ``get_request_matcher``."""

_DONE: Final = "[done]"
"""The choice that ends the picking."""

_DEFAULT_MATCHERS: Final = ("method", "isjson")
"""What a parser claims requests by when nothing may be asked and none is named."""


@final
@dataclass(frozen=True, slots=True)
class RequestMatcherChoice:
    """One matcher a parser may claim its sender's requests with.

    Attributes:
        name: What it is picked by: its class name without ``RequestMatcher``.
        arguments: Its constructor's arguments, as source — placeholders that
            build one, for the application to replace. ``_SIGNATURE_HEADER`` is the
            header constant the generated parser declares.
    """

    name: str
    arguments: str

    @property
    def class_name(self) -> str:
        """The matcher's class: ``Method`` → ``MethodRequestMatcher``."""
        return f"{self.name}RequestMatcher"


REQUEST_MATCHERS: Final = (
    RequestMatcherChoice("Attributes", '{"type": ".+"}'),
    RequestMatcherChoice("Callable", "lambda _request: True"),
    RequestMatcherChoice("Header", "_SIGNATURE_HEADER"),
    RequestMatcherChoice("Host", 'r"^hooks\\.example\\.com$"'),
    RequestMatcherChoice("Ips", '["192.0.2.0/24"]'),
    RequestMatcherChoice("IsJson", ""),
    RequestMatcherChoice("Method", '"POST"'),
    RequestMatcherChoice("Path", '"^/webhook/"'),
    RequestMatcherChoice("Port", "443"),
    RequestMatcherChoice("QueryParameter", '"token"'),
    RequestMatcherChoice("Scheme", '"https"'),
)
"""Every matcher offered, in the order offered."""

_BY_NAME: Final = {choice.name.lower(): choice for choice in REQUEST_MATCHERS}


def pick_request_matchers(
    io: ConsoleStyle, typed: Sequence[str] | None
) -> tuple[RequestMatcherChoice, ...]:
    """Return the matchers ``typed`` names, else the ones picked, else the method and JSON ones.

    A name matches without case, with or without ``RequestMatcher``, and a
    matcher named twice is taken once. Picking offers ``[done]`` and every
    matcher not taken yet, one question at a time, until ``[done]``.

    Raises:
        InvalidArgumentError: When ``typed`` names a matcher that is not offered.
    """
    if typed:
        picked: dict[str, RequestMatcherChoice] = {}
        for typed_name in typed:
            choice = _BY_NAME.get(typed_name.strip().lower().removesuffix("requestmatcher"))
            if choice is None:
                offered = ", ".join(offered.name for offered in REQUEST_MATCHERS)
                raise InvalidArgumentError(
                    f"There is no request matcher {typed_name!r}; the ones offered are {offered}."
                )
            _ = picked.setdefault(choice.name, choice)
        return tuple(picked.values())
    if not io.interactive:
        return tuple(_BY_NAME[name] for name in _DEFAULT_MATCHERS)
    chosen: list[RequestMatcherChoice] = []
    while remaining := [choice for choice in REQUEST_MATCHERS if choice not in chosen]:
        answer = io.ask(
            f"A request matcher the sender's requests must pass, or [cyan]{escape(_DONE)}[/]",
            _DONE,
            choices=(_DONE, *(choice.name for choice in remaining)),
        )
        if answer == _DONE:
            break
        chosen.append(_BY_NAME[answer.lower()])
    return tuple(chosen)


def request_matcher_body(chosen: Sequence[RequestMatcherChoice], imports: ImportCollector) -> str:
    """Return the ``return`` statement of ``get_request_matcher``, indented, and import its names.

    One matcher is returned as it is. Several are chained, one per line with
    trailing commas, so the formatter keeps them that way however many there
    are; none is an empty chain — which claims every request — with a comment
    saying so.
    """
    built = [f"{imports.add(_MODULE, choice.class_name)}({choice.arguments})" for choice in chosen]
    if len(built) == 1:
        return f"{_BODY}return {built[0]}"
    chain = imports.add(_MODULE, "ChainRequestMatcher")
    if not built:
        return (
            f"{_BODY}# An empty chain claims every request: add what tells the sender's apart.\n"
            f"{_BODY}return {chain}([])"
        )
    items = "".join(f"{_BODY}        {matcher},\n" for matcher in built)
    return f"{_BODY}return {chain}(\n{_BODY}    [\n{items}{_BODY}    ],\n{_BODY})"
