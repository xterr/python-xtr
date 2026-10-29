"""Function listeners, found by the event dispatcher bundle in the scan.

Neither a listener nor a subscriber is registered by hand. The event dispatcher bundle finds
``@as_event_listener`` functions and every ``EventSubscriberInterface`` class in the scan, and
hands them to the container's dispatcher in priority order.
"""

from __future__ import annotations

__all__: list[str] = []
