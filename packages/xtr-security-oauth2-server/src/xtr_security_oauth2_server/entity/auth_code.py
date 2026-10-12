"""The authorization-code entity a grant issues and the token endpoint redeems."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server.entities.auth_code_entity_interface import AuthCodeEntityInterface
from xtr_security_oauth2_server.entities.traits.auth_code_trait import AuthCodeTrait
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server.entities.traits.token_entity_trait import TokenEntityTrait

__all__ = ["AuthCode"]


@final
class AuthCode(EntityTrait, TokenEntityTrait, AuthCodeTrait, AuthCodeEntityInterface):
    """An authorization code, remembering the redirect URI it was asked for.

    The redirect URI is what the token endpoint compares the token request
    against, so a code intercepted on one registered URI cannot be redeemed
    naming another.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """
