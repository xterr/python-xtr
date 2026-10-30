"""Class hierarchies carried through serialization: events as dataclasses, notices as models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from pydantic import AwareDatetime, BaseModel, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

from xtr_serializer import discriminator_map, discriminator_name

__all__ = [
    "Alert",
    "Batch",
    "Board",
    "Bounce",
    "Circle",
    "Complaint",
    "Delivery",
    "Drawing",
    "Event",
    "Failure",
    "Mailbox",
    "Notice",
    "Outage",
    "Reminder",
    "Shape",
    "Square",
    "Unnamed",
]

# What a model of the hierarchy is: exact, closed to fields it does not declare, frozen.
_CLOSED = ConfigDict(strict=True, extra="forbid", frozen=True, ser_json_bytes="base64")
_CLOSED_DATACLASS = ConfigDict(strict=True, extra="forbid")


@discriminator_name("event")
@discriminator_map()
@dataclass(frozen=True)
class Event:
    """The base of a hierarchy, registered itself: a value may be just an event."""

    name: str


@discriminator_name("delivery")
@dataclass(frozen=True)
class Delivery(Event):
    recipient: str
    at: datetime


@dataclass(frozen=True)
class Failure(Event):
    """An intermediate class with no name: only its subclasses are ever written."""

    reason: str


@discriminator_name("bounce")
@dataclass(frozen=True)
class Bounce(Failure):
    code: int


@discriminator_name("complaint")
@dataclass(frozen=True)
class Complaint(Failure):
    feedback: str | None = None

    def __post_init__(self) -> None:
        # Runs on reading too: a dataclass the hierarchy holds keeps its own checks.
        if self.feedback == "":
            msg = "feedback is absent or says something"
            raise ValueError(msg)


@discriminator_name("batch")
@dataclass(frozen=True)
class Batch(Event):
    """Events holding events: the hierarchy inside itself."""

    events: tuple[Event, ...] = ()
    failures: list[Failure] = field(default_factory=list[Failure])


@dataclass(frozen=True)
class Unnamed(Delivery):
    """A subclass never given a name, so never written."""


@dataclass(frozen=True)
class Mailbox:
    """Every place a hierarchy's value sits in."""

    latest: Event
    failures: list[Failure]
    by_id: dict[str, Event]
    maybe: Event | None
    pair: tuple[Delivery, Failure]


@discriminator_name("notice")
@discriminator_map()
class Notice(BaseModel):
    model_config: ClassVar[ConfigDict] = _CLOSED

    title: str


@discriminator_name("reminder")
class Reminder(Notice):
    due: AwareDatetime


class Alert(Notice):
    level: int


@discriminator_name("outage")
class Outage(Alert):
    region: str


class Board(BaseModel):
    model_config: ClassVar[ConfigDict] = _CLOSED

    pinned: Notice
    alerts: list[Alert]
    archive: tuple[Notice, ...] = ()


@discriminator_map()
@pydantic_dataclass(frozen=True, config=_CLOSED_DATACLASS)
class Shape:
    """Another hierarchy, of pydantic dataclasses, whose names another field never takes."""

    label: str


@discriminator_name("circle")
@pydantic_dataclass(frozen=True, config=_CLOSED_DATACLASS)
class Circle(Shape):
    radius: float


@discriminator_name("square")
@pydantic_dataclass(frozen=True, config=_CLOSED_DATACLASS)
class Square(Shape):
    side: float


@dataclass(frozen=True)
class Drawing:
    shapes: list[Shape]
