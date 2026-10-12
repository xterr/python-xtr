"""The name this package registers the services it keeps to itself under.

One name, declared once, because two spellings of it would drift apart. The
bundle registers this server's key loader, its JWS provider and the hasher a
client secret is kept under this qualifier rather than under the bare
interfaces — the self-issued-token package owns those, and a deployment
commonly runs both — and whatever else asks for one of them, a console command
included, names the same qualifier.
"""

from __future__ import annotations

from typing import Final

__all__ = ["SERVICE_QUALIFIER"]

SERVICE_QUALIFIER: Final = "oauth2_server"
"""What this package's own key material and password hasher are registered under."""
