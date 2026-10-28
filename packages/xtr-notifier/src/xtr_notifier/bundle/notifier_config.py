"""The one configuration an application writes to send notifications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import final

from xtr_notifier.exception import InvalidArgumentError
from xtr_notifier.notification import Importance

from .admin_recipient_config import AdminRecipientConfig

__all__ = ["NotifierConfig"]


def _no_transports() -> dict[str, str]:
    """The empty set of transports a zero-config application starts with."""
    return {}


def _no_policy() -> dict[str, Sequence[str]]:
    """The empty channel policy a zero-config application starts with."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class NotifierConfig:
    """Values the bundle builds the notifier, its channels and its senders from.

    Buildable with no arguments: the zero-config notifier has no channel, so
    it builds, boots and refuses to send until transports are configured.

    Attributes:
        chatter_transports: The chat transports, by name, each a DSN — or
            several joined by `` || `` (failover) or `` && `` (round robin).
            Configuring any brings the ``chat`` channel and the chatter. Pass a
            DSN through ``env("...")``: it carries credentials.
        texter_transports: The SMS and push transports, the same way. Configuring
            any brings the ``sms`` and ``push`` channels and the texter.
        channel_policy: The channels each importance goes to, for a notification
            naming none, keyed by the importance's value (``"urgent"``).
        admin_recipients: The administrators the application's own failures are
            reported to.
        notification_on_failed_messages: Whether a message the bus gave up on is
            reported to the administrators. Needs the messenger and event
            dispatcher bundles.
        http_client: The qualifier of the HTTP client providers are reached
            through — a scoped client of the HTTP client configuration; ``None``
            means the default one.
    """

    chatter_transports: Mapping[str, str] = field(default_factory=_no_transports)
    texter_transports: Mapping[str, str] = field(default_factory=_no_transports)
    channel_policy: Mapping[str, Sequence[str]] = field(default_factory=_no_policy)
    admin_recipients: Sequence[AdminRecipientConfig] = ()
    notification_on_failed_messages: bool = False
    http_client: str | None = None

    def __post_init__(self) -> None:
        """Refuse a policy keyed by something no notification can have.

        Raises:
            InvalidArgumentError: If a policy key is no importance's value.
        """
        known = tuple(importance.value for importance in Importance)
        for key in self.channel_policy:
            if key not in known:
                listed = '", "'.join(known)
                raise InvalidArgumentError(
                    f'The channel policy names "{key}", which is no importance; '
                    f'use one of "{listed}".'
                )
