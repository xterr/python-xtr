"""Adapters between the sending side and an actual HTTP client.

Kept apart from :mod:`xtr_webhook.server` because everything there imports
with no client installed. A bridge does not: it is reachable only once the
``client`` extra is present, which is what lets an application that only
receives webhooks avoid paying for sending them.
"""

from __future__ import annotations
