"""The client a grant reads while it handles one request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
from xtr_security_oauth2_server.entities.traits.client_trait import ClientTrait
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Client"]


@final
class Client(EntityTrait, ClientTrait, ClientEntityInterface):
    """A client, as the protocol sees it for the length of one request.

    Built empty and filled by the client repository out of what was stored,
    which is why the setters are here and the shipped traits carry readers
    only: a client arrives as a row, not as a constructor call.

    The grants it may use are a list of names rather than value objects,
    because this is the side the protocol compares against — a grant asks
    "may this client use *this* grant type" with the string it was handed.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """

    #: The grant types this client may use; empty means every one of them.
    _allowed_grant_types: tuple[str, ...] = ()

    #: Whether an unhashed code challenge is good enough for this client.
    _allow_plain_text_pkce: bool = False

    def set_name(self, name: str) -> None:
        """Set the name to show the resource owner when asking for consent."""
        self._name = name

    def set_redirect_uri(self, redirect_uri: Sequence[str]) -> None:
        """Register the URIs this client may be sent back to."""
        self._redirect_uri = redirect_uri

    def set_confidential(self, is_confidential: bool) -> None:
        """Record whether this client can keep a secret, and so must prove one."""
        self._is_confidential = is_confidential

    def is_plain_text_pkce_allowed(self) -> bool:
        """Tell whether this client may send an unhashed code challenge."""
        return self._allow_plain_text_pkce

    def set_allow_plain_text_pkce(self, allow_plain_text_pkce: bool) -> None:
        """Choose whether this client may send an unhashed code challenge."""
        self._allow_plain_text_pkce = allow_plain_text_pkce

    def set_allowed_grant_types(self, grant_types: Sequence[str]) -> None:
        """Allow this client exactly ``grant_types``, or every one when given none."""
        self._allowed_grant_types = tuple(grant_types)

    @override
    def supports_grant_type(self, grant_type: str) -> bool:
        """Tell whether this client is allowed to use ``grant_type``.

        A client registered for no grant in particular may use any of them,
        which is the registration a deployment gets when it says nothing. The
        trait this overrides answers the same for every grant; this reads the
        list once there is one.
        """
        if not self._allowed_grant_types:
            return True

        return grant_type in self._allowed_grant_types
