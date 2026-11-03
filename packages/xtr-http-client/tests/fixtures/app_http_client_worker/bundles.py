"""The application's root bundles: the HTTP client and the message bus, in every environment."""

from __future__ import annotations

from xtr_messenger.bundle import MessengerBundle

from xtr_http_client.bundle import HttpClientBundle

BUNDLES = {HttpClientBundle: {"all": True}, MessengerBundle: {"all": True}}
