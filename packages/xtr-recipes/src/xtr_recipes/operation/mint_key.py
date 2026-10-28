"""MintKey: writing a freshly minted private key where the recipe says it lives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

from xtr_recipes.file_write import write_text
from xtr_recipes.key_minting import mint_private_key

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MintKey"]


@final
@dataclass(frozen=True, slots=True)
class MintKey:
    """Mints a private key and writes it, readable by the owner alone.

    The key is minted when the step is applied rather than when it is planned,
    so a dry run costs no key and shows none. A file already at the path is
    never replaced: a key in place is what every token signed so far verifies
    against, so it is left alone even when it appeared after the plan was made.

    The lock does not record the file, so removing the package never deletes a
    key: it is a secret of the deployment, kept out of the repository by the
    recipe's ignore lines, and outlives the package that asked for it.

    Attributes:
        path: Where the key goes.
        display: How the path reads in the plan.
        algorithm: The signature algorithm the key is minted for.
        passphrase: What the key is encrypted with, or ``None`` for nothing.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    algorithm: str
    passphrase: str | None = None

    def render(self) -> tuple[str, ...]:
        """Return the line naming the key being minted, never the key itself."""
        return (f"  mint {self.display} ({self.algorithm})",)

    def apply(self) -> None:
        """Mint the key and write it ``0o600``, unless a file is already there."""
        if self.path.exists():
            return
        write_text(self.path, mint_private_key(self.algorithm, self.passphrase), private=True)
