"""A client reports its registration, and accepts every grant unless told otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ClientTrait"]


class ClientTrait:
    """Holds a client's registration and answers the grant-type question.

    The registration is protected state with readers only: the entity that
    composes this trait decides how it is filled — from a constructor, a row,
    or setters of its own — because that is where an application's clients
    actually come from.

    A client is public until it is told it is confidential, which is the safe
    default: a confidential client is made to prove a secret, and a
    misconfigured entity that claimed to be confidential while holding no
    secret could not be authenticated at all.

    Every grant type is supported unless the composing entity says otherwise.
    That is the default the contract promises, so an entity composing this
    trait satisfies the whole contract, and one that restricts its clients
    overrides a single method.
    """

    _name: str
    _redirect_uri: str | Sequence[str]
    _is_confidential: bool = False

    def get_name(self) -> str:
        """Return the name to show the resource owner when asking for consent."""
        return self._name

    def get_redirect_uri(self) -> str | Sequence[str]:
        """Return the registered redirect URI, or every one of them."""
        return self._redirect_uri

    def is_confidential(self) -> bool:
        """Tell whether this client can keep a secret, and so must prove one."""
        return self._is_confidential

    def supports_grant_type(self, grant_type: str) -> bool:
        """Tell whether this client is allowed to use ``grant_type``.

        Every one of them, until an entity composing this trait narrows it:
        this default answers the same whatever is asked, which is why the
        parameter goes unread here and is read by whoever overrides it.
        """
        del grant_type
        return True
