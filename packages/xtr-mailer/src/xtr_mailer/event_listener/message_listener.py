"""Adds default headers to every email, and renders its body."""

from __future__ import annotations

import copy
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import Message
from xtr_mime.header import Headers, MailboxListHeader

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError, MailerRuntimeError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_mime import BodyRendererInterface

    from xtr_mailer.event import MessageEvent

__all__ = ["MessageListener"]


@final
class MessageListener:
    """Gives every email the configured headers it lacks, then renders its body.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`. A default header the email does not carry is added. One it carries is
    handled by the rule for its name: :attr:`HEADER_SET_IF_EMPTY` (the rule for a name with
    none) keeps the email's, :attr:`HEADER_REPLACE` puts the default in its place, and
    :attr:`HEADER_ADD` adds the default beside it — or, for a header an email carries once,
    adds the default's addresses to the email's list. Each email gets its own copy of the
    defaults. Raw bytes are left as they are.
    """

    #: Run at the default priority, before the listeners signing the email.
    PRIORITY: Final = 0

    #: Keep the email's header; add the default only when the email has none of that name.
    HEADER_SET_IF_EMPTY: Final = 1
    #: Add the default beside the email's, or its addresses to the email's list.
    HEADER_ADD: Final = 2
    #: Put the default in place of the email's.
    HEADER_REPLACE: Final = 3

    #: An email's author and To stay its own; reply-to, Cc and Bcc addresses are added to.
    DEFAULT_RULES: Final[Mapping[str, int]] = MappingProxyType(
        {
            "from": HEADER_SET_IF_EMPTY,
            "return-path": HEADER_SET_IF_EMPTY,
            "reply-to": HEADER_ADD,
            "to": HEADER_SET_IF_EMPTY,
            "cc": HEADER_ADD,
            "bcc": HEADER_ADD,
        }
    )

    __slots__: ClassVar[tuple[str, ...]] = ("_header_rules", "_headers", "_renderer")

    def __init__(
        self,
        headers: Headers | None = None,
        renderer: BodyRendererInterface | None = None,
        header_rules: Mapping[str, int] = DEFAULT_RULES,
    ) -> None:
        """Add a copy of ``headers`` to every email by ``header_rules``, then render it.

        Args:
            headers: The default headers; ``None`` adds none.
            renderer: What renders each email's body once its headers are set; ``None``
                renders nothing.
            header_rules: The rule for each header name, whatever its case.

        Raises:
            InvalidArgumentError: A rule is not one of the three.
        """
        self._headers: Headers | None = None if headers is None else copy.copy(headers)
        self._renderer: BodyRendererInterface | None = renderer
        self._header_rules: dict[str, int] = {}
        for name, rule in header_rules.items():
            self.add_header_rule(name, rule)

    def add_header_rule(self, header_name: str, rule: int) -> None:
        """Handle a default header of ``header_name``, whatever its case, by ``rule``.

        Raises:
            InvalidArgumentError: ``rule`` is not one of the three.
        """
        if rule not in {self.HEADER_SET_IF_EMPTY, self.HEADER_ADD, self.HEADER_REPLACE}:
            raise InvalidArgumentError(f'The "{rule}" rule is not supported.')
        self._header_rules[header_name.lower()] = rule

    def on_message(self, event: MessageEvent) -> None:
        """Set the default headers on ``event``'s email, then render it.

        Raises:
            MailerRuntimeError: A default is to be added to a header an email carries once
                and that is not a list of addresses.
        """
        message = event.get_message()
        if not isinstance(message, Message):
            return
        if self._headers is not None:
            self._set_headers(message.get_headers(), self._headers)
        if self._renderer is not None:
            self._renderer.render(message)

    def _set_headers(self, headers: Headers, defaults: Headers) -> None:
        for default in defaults.all():
            name = default.get_name().lower()
            header = copy.deepcopy(default)
            rule = self._header_rules.get(name, self.HEADER_SET_IF_EMPTY)
            if not headers.has(name):
                _ = headers.add(header)
            elif rule == self.HEADER_REPLACE:
                headers.remove(name)
                _ = headers.add(header)
            elif rule == self.HEADER_ADD and not Headers.is_unique_header(name):
                _ = headers.add(header)
            elif rule == self.HEADER_ADD:
                existing = headers.get(name)
                if not isinstance(existing, MailboxListHeader) or not isinstance(
                    header, MailboxListHeader
                ):
                    raise MailerRuntimeError(f'Unable to set header "{shown(name)}".')
                for address in header.get_address_list():
                    existing.add_address(address)
