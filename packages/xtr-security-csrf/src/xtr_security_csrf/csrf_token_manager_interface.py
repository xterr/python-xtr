"""The one surface every token manager answers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .csrf_token import CsrfToken

__all__ = ["CsrfTokenManagerInterface"]


@runtime_checkable
class CsrfTokenManagerInterface(Protocol):
    """Mints, renews, drops and checks tokens, by id.

    Every member is awaited: a manager reaches a storage to answer any of
    them, and one storage must be swappable for another — a remote one is
    awaited — exactly as every matcher is awaited even when it only reads
    the head of a request.
    """

    async def get_token(self, token_id: str) -> CsrfToken:
        """Return the token for ``token_id``, minting one where none is stored.

        A token already stored is returned with the value it holds — the
        same stored value, though not the same string, since what is handed
        out is masked per call — so asking twice answers two tokens that
        both check out.
        """
        ...

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh value for ``token_id``, stored or not.

        For once-only tokens, in places with high security needs: whatever
        was stored under the id is replaced, independent of whether a value
        existed before.
        """
        ...

    async def remove_token(self, token_id: str) -> str | None:
        """Drop the token under ``token_id``, if one is stored.

        Returns:
            The value the id held, or ``None`` when it held nothing.
        """
        ...

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Tell whether ``token`` carries the value stored under its id.

        Never raises on the value it is handed: one that does not read as
        a value this manager minted simply does not check out.
        """
        ...
