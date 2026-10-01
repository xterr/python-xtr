"""The shared behaviour of a key loader: raw strings or file paths."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .key_loader_interface import KeyLoaderInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["AbstractKeyLoader"]


class AbstractKeyLoader(  # pyright: ignore[reportImplicitAbstractClass]  -- RawKeyLoader implements load_key
    KeyLoaderInterface,
):
    """Reads a signing or verifying key from a raw string or a file path.

    The signing key and the public key may each be given either as the key text
    itself or as the path of a file holding it — an existing file wins, so a key
    that happens to look like a path is still read from disk when that path
    exists. The additional public keys, by contrast, must each be a readable
    file: they are the keys of other issuers a deployment trusts, kept on disk.

    Concrete subclasses turn the text this returns into keys; this class only
    decides where the text comes from.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_additional_public_keys",
        "_passphrase",
        "_public_key",
        "_signing_key",
    )

    def __init__(
        self,
        signing_key: str | None,
        public_key: str | None,
        passphrase: str | None = None,
        additional_public_keys: Sequence[str] = (),
    ) -> None:
        """Record the signing key, public key, pass phrase and extra public keys."""
        self._signing_key: str | None = signing_key
        self._public_key: str | None = public_key
        self._passphrase: str | None = passphrase
        self._additional_public_keys: tuple[str, ...] = tuple(additional_public_keys)

    @override
    def get_signing_key(self) -> str | None:
        """Return the private key text, reading a file when the value is a path."""
        return self._read(self._signing_key)

    @override
    def get_public_key(self) -> str | None:
        """Return the public key text, reading a file when the value is a path."""
        return self._read(self._public_key)

    @override
    def get_passphrase(self) -> str | None:
        """Return the pass phrase the private key is encrypted with, if any."""
        return self._passphrase

    @override
    def get_additional_public_keys(self) -> Sequence[str]:
        """Return the extra public keys, each read from its file.

        Raises:
            InvalidArgumentError: When any configured path is not a readable file.
        """
        keys: list[str] = []
        for path in self._additional_public_keys:
            file = Path(path)
            if not file.is_file():
                raise InvalidArgumentError(
                    f"The additional public key {path!r} is not a readable file.",
                )
            keys.append(file.read_text(encoding="utf-8"))
        return tuple(keys)

    @staticmethod
    def _read(value: str | None) -> str | None:
        """Return ``value`` itself, or the contents of the file it names."""
        if value is None:
            return None
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return value
