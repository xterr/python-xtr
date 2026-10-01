"""A hasher that hashes with the best and verifies the legacy ones too."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

__all__ = ["MigratingPasswordHasher"]


@final
class MigratingPasswordHasher(PasswordHasherInterface):
    """Hashes with one preferred hasher, verifies with it and older ones behind it.

    A deployment holding hashes from several eras keeps this in front: new
    passwords are hashed with ``best``, and a stored hash ``best`` does not
    recognise is offered to each of ``extras`` in turn. A hash ``best`` already
    owns never reaches the extras, so the common path pays for one verify.

    Paired with :meth:`needs_rehash` — which delegates to ``best`` — a login
    verified against a legacy hash is the moment to rehash and upgrade it.
    """

    __slots__ = ("_best", "_extras")

    def __init__(
        self,
        best: PasswordHasherInterface,
        *extras: PasswordHasherInterface,
    ) -> None:
        """Hash with ``best``; fall back to ``extras`` only for hashes it disowns."""
        self._best = best
        self._extras = extras

    @override
    def hash(self, plain: str) -> str:
        """Hash ``plain`` with the preferred hasher.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
        """
        return self._best.hash(plain)

    @override
    def verify(self, hashed: str, plain: str) -> bool:
        """Return whether ``plain`` made ``hashed``, trying the best then the extras.

        When ``best`` recognises ``hashed`` — it does not need rehashing to the
        best format — only ``best`` verifies it. Otherwise each extra is tried,
        then ``best`` once more as a last resort.
        """
        if not self._best.needs_rehash(hashed):
            return self._best.verify(hashed, plain)
        for extra in self._extras:
            if extra.verify(hashed, plain):
                return True
        return self._best.verify(hashed, plain)

    @override
    def needs_rehash(self, hashed: str) -> bool:
        """Return whether ``hashed`` should be replaced, as the best hasher sees it."""
        return self._best.needs_rehash(hashed)
