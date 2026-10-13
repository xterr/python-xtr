"""What the clients of this package share, and nobody outside it should import.

The option handling a client does before a connection is opened — merging a
request's options over the client's defaults and refusing a name no client
knows — reaches callers through
:class:`HttpClientMixin <xtr_http_client.http_client_mixin.HttpClientMixin>`,
which is the one supported way in. These modules are where it is written; they
move without notice.
"""

from __future__ import annotations

__all__: list[str] = []
