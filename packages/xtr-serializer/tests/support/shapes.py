"""The values the support normalizers write and read: a point, and objects made of points."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Parcel", "Point", "Segment"]


@dataclass(frozen=True, slots=True)
class Point:
    """A point on a grid, written as its two coordinates."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Segment:
    """Two points: an object whose parts another normalizer writes."""

    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class Parcel:
    """A point carried inside other data as text the serializer already wrote."""

    content: Point
