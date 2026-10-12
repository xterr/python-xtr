"""What a stored client answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.value_object.grant import Grant
    from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ClientInterface"]


@runtime_checkable
class ClientInterface(Protocol):
    """A client as this server keeps it: a registration, and a secret or not.

    This is the stored side of a client. The library's own client entity is
    the other side — what a grant reads while it handles a request — and the
    client repository builds one from the other. Keeping them apart is what
    lets an application map its clients however it likes while the protocol
    sees one shape.

    The setters answer the client so a caller can chain them, which is how a
    command registering a client reads: name it, point it at its redirect
    URIs, allow it its grants, in one expression.

    A client is confidential when it holds a secret, and the secret it holds
    is a hash — nothing in this package ever stores or compares a plaintext
    one.
    """

    def get_identifier(self) -> str:
        """Return the identifier this client is registered under."""
        ...

    def get_name(self) -> str:
        """Return the name to show the resource owner when asking for consent."""
        ...

    def set_name(self, name: str) -> Self:
        """Rename this client ``name``."""
        ...

    def get_secret(self) -> str | None:
        """Return the hash of this client's secret, or ``None`` when it has none."""
        ...

    def set_secret(self, secret: str) -> None:
        """Replace the hash of this client's secret.

        Answers nothing, unlike the other setters: this is the one write that
        is never part of registering a client — it is the rehash a successful
        authentication triggers — so there is nothing to chain onto it.
        """
        ...

    def get_redirect_uris(self) -> Sequence[RedirectUri]:
        """Return every redirect URI this client may be sent back to."""
        ...

    def set_redirect_uris(self, *redirect_uris: RedirectUri) -> Self:
        """Register ``redirect_uris`` as the ones this client may be sent back to."""
        ...

    def get_grants(self) -> Sequence[Grant]:
        """Return the grants this client may use, or nothing for every grant."""
        ...

    def set_grants(self, *grants: Grant) -> Self:
        """Allow this client exactly ``grants``, or every grant when given none."""
        ...

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes this client may ask for, or nothing for any scope."""
        ...

    def set_scopes(self, *scopes: Scope) -> Self:
        """Allow this client exactly ``scopes``, or any scope when given none."""
        ...

    def is_active(self) -> bool:
        """Tell whether this client may authenticate at all."""
        ...

    def set_active(self, active: bool) -> Self:
        """Let this client authenticate, or stop it from doing so."""
        ...

    def is_confidential(self) -> bool:
        """Tell whether this client holds a secret, and so must prove one."""
        ...

    def is_plain_text_pkce_allowed(self) -> bool:
        """Tell whether this client may send an unhashed code challenge."""
        ...

    def set_allow_plain_text_pkce(self, allow_plain_text_pkce: bool) -> Self:
        """Choose whether this client may send an unhashed code challenge."""
        ...
