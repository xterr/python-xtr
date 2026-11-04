"""What every report from a mail provider says, whichever report it is."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from xtr_remote_event.remote_event import RemoteEvent

__all__ = ["AbstractMailerEvent"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AbstractMailerEvent(RemoteEvent):
    """The facts every mail provider's report carries, on top of the three of any event.

    Providers report the same facts under different keys and in different
    shapes — a timestamp here, a date string there, the address as
    ``recipient`` or as ``email``. A payload converter reads them into these
    fields once, so a consumer handles every provider's reports without knowing
    which provider sent them; whatever else the provider said stays in
    ``payload``.

    Abstract: a report is about either a delivery or an engagement, and this
    class only holds what the two share. Building it rather than a type derived
    from it raises ``TypeError``, as building an abstract class does.

    What it adds is passed by keyword, so the three inherited fields keep their
    positions and a field with a default never has to come before one without.
    Frozen like the base, with the same reach: the freeze binds ``metadata``,
    not the mapping behind it.

    Each type derived from it registers the name it is written under, so a
    report crosses a message bus as its own type; this one registers none,
    since no value of it is ever built.

    Attributes:
        date: When the provider says it happened, which is not when the report
            arrived: providers retry and batch their reports. A ``datetime``,
            written with its offset: one in a named zone comes back in that
            offset, and one in the hour the clocks repeat is refused when
            written, so give it in UTC as providers report it.
        recipient_email: The address the report is about, or ``""`` when the
            provider did not say.
        metadata: The values the mail was sent with for the application's own
            use, as the provider hands them back — what ties a report to the
            application's records. JSON data, as the payload is.
        tags: The labels the mail was sent with.
    """

    date: datetime
    recipient_email: str = ""
    metadata: dict[str, object] = field(default_factory=dict[str, object])
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse to build this class itself, since it stands for no report of its own.

        Raises:
            TypeError: When the event being built is this class rather than a
                type derived from it.
        """
        if type(self) is AbstractMailerEvent:
            raise TypeError(
                '"AbstractMailerEvent" is abstract: build a "MailerDeliveryEvent" or a '
                '"MailerEngagementEvent" instead.'
            )
