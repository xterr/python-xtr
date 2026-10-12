"""What a registered client answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ClientEntityInterface"]


@runtime_checkable
class ClientEntityInterface(Protocol):
    """The application a token is issued to.

    A client is identified, named for a consent screen, registered with the
    redirect URIs it may be sent back to, and either confidential — able to
    keep a secret, so it is made to prove one — or public.

    :meth:`supports_grant_type` is part of the contract rather than an optional
    extra a grant has to probe for: the shipped client trait answers ``True``,
    so an implementation composing it says "every grant" without writing a
    line, and one that restricts its clients overrides a method the type
    checker already knows about. A grant can then simply ask.
    """

    def get_identifier(self) -> str:
        """Return the identifier this client is registered under."""
        ...

    def get_name(self) -> str:
        """Return the name to show the resource owner when asking for consent."""
        ...

    def get_redirect_uri(self) -> str | Sequence[str]:
        """Return the registered redirect URI, or every one of them.

        A client registered with a single URI may hand back that string; one
        registered with several hands back a sequence. A reader tests for
        ``str`` first, because a string is itself a sequence of strings.
        """
        ...

    def is_confidential(self) -> bool:
        """Tell whether this client can keep a secret, and so must prove one."""
        ...

    def supports_grant_type(self, grant_type: str) -> bool:
        """Tell whether this client is allowed to use ``grant_type``."""
        ...
