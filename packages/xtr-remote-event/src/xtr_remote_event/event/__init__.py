"""Event types derived from the remote event, for the reports a whole kind of sender makes.

Every mail provider reports deliveries, bounces and opens, each in its own words. A type for
such reports, with the facts they share as fields, lets a consumer be written once for the kind
of sender rather than once per sender.
"""

from __future__ import annotations

from .mailer import AbstractMailerEvent, MailerDeliveryEvent, MailerEngagementEvent

__all__ = ["AbstractMailerEvent", "MailerDeliveryEvent", "MailerEngagementEvent"]
