"""Notifications: what happened, how much it matters, and where it is sent.

The interfaces a notification implements to render its own message —
``ChatNotificationInterface``, ``SmsNotificationInterface`` and
``PushNotificationInterface`` — are imported from their own modules: they name
the message types, which carry a :class:`NotificationSummary`, so re-exporting
them here would make the two packages import each other.
"""

from __future__ import annotations

from .importance import Importance
from .notification import Notification
from .notification_summary import NotificationSummary

__all__ = ["Importance", "Notification", "NotificationSummary"]
