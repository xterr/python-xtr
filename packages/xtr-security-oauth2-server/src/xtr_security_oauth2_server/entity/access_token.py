"""The access-token entity a grant issues and a token signs itself from."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
    AccessTokenEntityInterface,
)
from xtr_security_oauth2_server_core.entities.traits.access_token_trait import AccessTokenTrait
from xtr_security_oauth2_server_core.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server_core.entities.traits.token_entity_trait import TokenEntityTrait

__all__ = ["AccessToken"]


@final
class AccessToken(EntityTrait, TokenEntityTrait, AccessTokenTrait, AccessTokenEntityInterface):
    """An access token the grants fill in and the token endpoint signs.

    Three traits and nothing of its own: an identifier, what the token is for,
    and the ability to sign itself into the document a resource server reads.

    The contract comes last of the bases on purpose, and every entity here is
    written the same way: the stubs a contract declares are real methods that
    answer nothing, so a contract listed before the traits would shadow the
    accessors the traits bring and every reader would come back empty.

    It takes no constructor arguments, because the access-token repository
    mints one and then fills it — including the extra claims a listener asked
    for, which go on through
    :meth:`~xtr_security_oauth2_server_core.entities.traits.access_token_trait.AccessTokenTrait.set_extra_claims`
    so the reserved names are refused where they are set rather than where
    they are signed.
    """
