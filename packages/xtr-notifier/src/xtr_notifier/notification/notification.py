"""What happened, how much it matters, and where to say it."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, ClassVar, assert_never

from xtr_logging_contracts import Level

from .importance import Importance

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging_contracts import LevelLike

    from xtr_notifier.recipient import RecipientInterface

__all__ = ["Notification"]


class Notification:
    """A notification: a subject, a body, an importance, and the channels it goes to.

    Built in one call with keywords and read through properties, so one
    notification sent to several recipients is the same notification for each
    of them. An application customises it by subclassing: override
    :meth:`get_channels` to pick channels per recipient, or implement a
    ``as_chat_message`` / ``as_sms_message`` / ``as_push_message`` hook to
    render a channel's message itself.

    Without channels, the notifier asks its channel policy which channels the
    importance calls for.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_channels",
        "_content",
        "_emoji",
        "_exception",
        "_exception_as_string",
        "_importance",
        "_subject",
    )

    _subject: str
    _content: str
    _importance: Importance
    _emoji: str
    _channels: tuple[str, ...]
    _exception: BaseException | None
    _exception_as_string: str

    def __init__(  # noqa: PLR0913 -- every field is a keyword, as one call builds a whole notification
        self,
        subject: str = "",
        *,
        content: str = "",
        importance: Importance = Importance.HIGH,
        emoji: str = "",
        channels: Sequence[str] = (),
        exception: BaseException | None = None,
    ) -> None:
        """Describe what happened.

        Args:
            subject: The one-line summary every channel shows.
            content: The longer text, for the channels that show one.
            importance: How much it matters; a channel policy maps it to channels.
            emoji: Shown beside the subject by the channels that show one.
                Left empty, a notification about an exception takes one from
                its importance.
            channels: The channels to send to (``"chat"``, ``"sms"``), each
                optionally naming a transport (``"chat/slack"``). Empty leaves
                the choice to the channel policy.
            exception: An error the notification reports. Replaces ``subject``
                with the error's type and message, and keeps its traceback.
        """
        self._subject = subject
        self._content = content
        self._importance = importance
        self._emoji = emoji
        self._channels = tuple(channels)
        self._exception = exception
        self._exception_as_string = ""
        if exception is not None:
            self._subject = f"{type(exception).__name__}: {exception}"
            self._exception_as_string = "".join(traceback.format_exception(exception)).rstrip()

    @classmethod
    def from_exception(cls, exception: BaseException, channels: Sequence[str] = ()) -> Notification:
        """Build a notification reporting ``exception``, to ``channels``."""
        return cls(channels=channels, exception=exception)

    @staticmethod
    def importance_from_level(level: LevelLike) -> Importance:
        """Return the importance a log level calls for.

        Critical and above is urgent, error is high, anything lower is low — so
        a notification raised from a log record matches how loud the record was.

        Raises:
            InvalidLevelError: If ``level`` names no log level.
        """
        parsed = Level.parse(level)
        if parsed >= Level.CRITICAL:
            return Importance.URGENT
        if parsed >= Level.ERROR:
            return Importance.HIGH
        return Importance.LOW

    @property
    def subject(self) -> str:
        """The one-line summary every channel shows."""
        return self._subject

    @property
    def content(self) -> str:
        """The longer text, for the channels that show one."""
        return self._content

    @property
    def importance(self) -> Importance:
        """How much the notification matters."""
        return self._importance

    @property
    def emoji(self) -> str:
        """The emoji given, or one matching the importance when an exception is reported."""
        return self._emoji or self._default_emoji()

    @property
    def exception(self) -> BaseException | None:
        """The error the notification reports, if any."""
        return self._exception

    @property
    def exception_as_string(self) -> str:
        """The reported error's traceback, or ``""``."""
        return self._exception_as_string

    @property
    def channels(self) -> tuple[str, ...]:
        """The channels the notification was built with."""
        return self._channels

    def get_channels(self, recipient: RecipientInterface) -> tuple[str, ...]:
        """Return the channels to send to ``recipient`` on.

        The same channels for everyone unless a subclass says otherwise; an
        empty answer leaves the choice to the channel policy.
        """
        del recipient
        return self._channels

    def _default_emoji(self) -> str:
        """Return the emoji the importance calls for, when an exception is reported."""
        if not self._exception_as_string:
            return ""
        match self._importance:
            case Importance.URGENT:
                return "🌩️"
            case Importance.HIGH:
                return "🌧️"
            case Importance.MEDIUM:
                return "🌦️"
            case Importance.LOW:
                return "⛅"
            case _:
                # An importance added without an emoji fails here, not on a send.
                assert_never(self._importance)
