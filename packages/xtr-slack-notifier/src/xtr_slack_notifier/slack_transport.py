"""Posting chat messages to Slack through its Web API."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, Final, final
from urllib.parse import urlencode

from typing_extensions import override
from xtr_http_client_contracts.exception import TransportError as HttpTransportError
from xtr_notifier.exception import (
    InvalidArgumentError,
    TransportError,
    UnsupportedMessageTypeError,
)
from xtr_notifier.message import ChatMessage
from xtr_notifier.transport import AbstractTransport

from .slack_options import SlackOptions
from .slack_sent_message import SlackSentMessage
from .update_message_slack_options import UpdateMessageSlackOptions

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_notifier.message import MessageInterface

__all__ = ["SlackTransport"]

_TOKEN: Final = re.compile(r"^xox(b-|p-|a-2)")
_KINDS: Final = frozenset({SlackOptions.KIND, UpdateMessageSlackOptions.KIND})


@final
class SlackTransport(AbstractTransport):
    """Posts, schedules and updates messages through Slack's Web API.

    The channel a message goes to is the one its options name, else its
    recipient, else the channel the transport was built with. A message made
    from a notification and carrying no options is rendered by
    :meth:`SlackOptions.from_notification`. Options of the ``slack.update``
    kind call ``chat.update``; a ``post_at`` field calls
    ``chat.scheduleMessage``; anything else ``chat.postMessage``.
    """

    HOST: ClassVar[str] = "slack.com"

    def __init__(
        self,
        access_token: str,
        channel: str | None,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Post with ``access_token`` to ``channel`` unless a message names its own.

        Args:
            access_token: A bot (``xoxb-``), user (``xoxp-``) or app (``xoxa-2``)
                token; never shown.
            channel: The channel posted to when a message names none, or ``None``.
            http_client: What the Web API is reached through.
            event_dispatcher: Where the message events go; ``None`` announces nothing.

        Raises:
            InvalidArgumentError: When the token is not of a kind Slack issues.
        """
        if not _TOKEN.match(access_token):
            raise InvalidArgumentError(
                'A valid Slack token needs to start with "xoxb-", "xoxp-" or "xoxa-2". '
                "See https://api.slack.com/authentication/token-types for further information."
            )
        super().__init__(http_client, event_dispatcher)
        self._access_token = access_token
        self._channel = channel

    @override
    def __str__(self) -> str:
        """Name the endpoint and the channel; never the token."""
        name = f"slack://{self._get_endpoint()}"
        return f"{name}?{urlencode({'channel': self._channel})}" if self._channel else name

    @override
    def __repr__(self) -> str:
        """Render as the string form, so a traceback never shows the token."""
        return f"{type(self).__name__}({str(self)!r})"

    @override
    def supports(self, message: MessageInterface) -> bool:
        """Send chat messages carrying no options, Slack's, or Slack update options."""
        return isinstance(message, ChatMessage) and (
            message.options is None or message.options.kind in _KINDS
        )

    @override
    async def _do_send(self, message: MessageInterface) -> SlackSentMessage:
        """Call the method the options pick, and report the channel and ``ts`` posted at.

        Raises:
            UnsupportedMessageTypeError: When ``message`` is not a chat message.
            TransportError: When the Web API cannot be reached or refuses the message.
        """
        if not isinstance(message, ChatMessage):
            raise UnsupportedMessageTypeError(str(self), "ChatMessage", message)
        options = message.options
        if options is None and message.notification is not None:
            options = SlackOptions.from_notification(message.notification).to_options()
        fields = {} if options is None else dict(options.values)
        if fields.get("channel") is None:
            fields["channel"] = message.recipient_id or self._channel
        fields["text"] = message.subject
        method = (
            "chat.update"
            if options and options.kind == UpdateMessageSlackOptions.KIND
            else "chat.postMessage"
        )
        if "post_at" in fields:
            method = "chat.scheduleMessage"
        answer = await self._call(method, fields)
        return SlackSentMessage(message, str(self), str(answer["channel"]), str(answer["ts"]))

    async def _call(self, method: str, fields: Mapping[str, object]) -> Mapping[str, object]:
        """Call ``method`` with the fields that are not empty, and return what it answered."""
        url = f"{self._get_http_scheme()}://{self._get_endpoint()}/api/{method}"
        try:
            response = await self._http_client.request(
                "POST",
                url,
                json={key: value for key, value in fields.items() if not _is_empty(value)},
                auth_bearer=self._access_token,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        except HttpTransportError as error:
            raise TransportError("Could not reach the remote Slack server.") from error
        async with response:
            if response.get_status_code() != HTTPStatus.OK:
                content = (await response.get_content(throw=False)).decode(errors="replace")
                raise TransportError(f'Unable to post the Slack message: "{content}".', response)
            answer = await response.to_array(throw=False)
        if not answer.get("ok"):
            errors = answer.get("errors")
            listed = (
                f" ({'|'.join(map(str, errors))})"
                if isinstance(errors, Sequence) and not isinstance(errors, str)
                else ""
            )
            raise TransportError(
                f'Unable to post the Slack message: "{answer.get("error")}"{listed}.', response
            )
        return answer


def _is_empty(value: object) -> bool:
    """Tell whether ``value`` is left out of a request: ``None``, ``""`` or an empty collection.

    ``False`` and ``0`` are values, and are sent.
    """
    if value is None or value == "":
        return True
    return isinstance(value, (Mapping, Sequence)) and not value
