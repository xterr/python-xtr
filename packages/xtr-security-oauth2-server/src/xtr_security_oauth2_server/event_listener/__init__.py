"""The listeners this package ships, for the rules it holds itself to.

One so far: a client registered with no scopes gets the deployment's default
ones. It lives here rather than inside a manager because every client manager
announces its saves, so the rule is written once and holds wherever a client
is registered from.

Nothing here wires itself. The bundle registers these listeners, so an
application that never activated it runs none of them.
"""

from __future__ import annotations

from .add_client_default_scopes_listener import AddClientDefaultScopesListener

__all__ = ["AddClientDefaultScopesListener"]
