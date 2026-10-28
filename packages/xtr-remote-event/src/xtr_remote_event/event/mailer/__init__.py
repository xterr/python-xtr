"""A mail provider's reports on a message: how its delivery went, and what its recipient did.

A payload converter reads a provider's report into one of these rather than into a bare
:class:`~xtr_remote_event.RemoteEvent`, so a consumer of mail reports is written once and works
with every provider.
"""

from __future__ import annotations

from .abstract_mailer_event import AbstractMailerEvent
from .mailer_delivery_event import MailerDeliveryEvent
from .mailer_engagement_event import MailerEngagementEvent

__all__ = ["AbstractMailerEvent", "MailerDeliveryEvent", "MailerEngagementEvent"]
