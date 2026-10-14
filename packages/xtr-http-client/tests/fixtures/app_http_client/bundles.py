"""The application's root bundles: only HttpClientBundle, in every environment."""

from __future__ import annotations

from xtr_http_client.bundle import HttpClientBundle

BUNDLES = {HttpClientBundle: {"all": True}}
