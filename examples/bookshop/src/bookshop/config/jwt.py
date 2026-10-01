"""The JWT bundle: the signing key, how long a token lives, and the claim the user is named by.

The JWT bundle is an add-on — it has no zero-config path — so this module is not optional: it
must name a signing key or the build fails with an ``InvalidConfigurationError`` pointing right
here. ``secret_key`` takes the key text or a path to it; the bundle's key loader reads the file
itself, so this passes the path, resolved with ``resolve:`` (which expands the
``%kernel.project_dir%`` in ``JWT_SECRET_KEY_PATH``, the way ``SHOP_LOG_PATTERN`` is resolved),
never the key material inline.

``user_id_claim`` is the claim the user's identifier is written into when a token is minted and
read back from when one is presented; ``token_ttl`` is how long a minted token lives.
"""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_security_jwt.bundle import JwtConfig

__all__ = ["jwt"]


@configure
def jwt() -> JwtConfig:
    """Sign with the key minted into ``secrets/``; name the user by ``sub``; tokens live an hour."""
    return JwtConfig(
        secret_key=env("resolve:JWT_SECRET_KEY_PATH"),
        token_ttl=3600,
        user_id_claim="sub",
    )
