"""The container parameters this bundle sets, and its compiler passes read.

They are named in one place because they are the seam between the bundle and
its passes: the bundle writes them while services are being defined, and a pass
reads their final values once every bundle has had its say — which is the whole
point of a pass, since an application may have overridden one in between.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "ACCESS_TOKEN_TTL_DEFAULT",
    "ENCRYPTION_KEY",
    "ENCRYPTION_KEY_TYPE",
    "PERSISTENCE_ORM_CONNECTION",
    "PERSISTENCE_ORM_ENABLED",
    "SCOPES_DEFAULT",
]

#: The password, or the base64url of a key's bytes, that this server's own
#: payloads are sealed with.
ENCRYPTION_KEY: Final = "oauth2_server.encryption_key"

#: Which of the two :data:`ENCRYPTION_KEY` is. A sibling leaf rather than
#: ``...encryption_key.type``: the parameter bag is a tree, so a name cannot be
#: both a value and the parent of another.
ENCRYPTION_KEY_TYPE: Final = "oauth2_server.encryption_key_type"

#: How long an access token lasts unless the grant issuing it was tagged with
#: something else.
ACCESS_TOKEN_TTL_DEFAULT: Final = "oauth2_server.access_token_ttl.default"  # noqa: S105 -- a parameter name, not a secret

#: The scopes a client registered with none is given.
SCOPES_DEFAULT: Final = "oauth2_server.scopes.default"

#: Whether this deployment keeps its clients and credentials in a database.
PERSISTENCE_ORM_ENABLED: Final = "oauth2_server.persistence.orm.enabled"

#: Which connection's tables they live in.
PERSISTENCE_ORM_CONNECTION: Final = "oauth2_server.persistence.orm.connection"
