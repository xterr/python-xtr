"""The shared behaviour of a key loader: raw strings or file paths."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .additional_public_key import AdditionalPublicKey
from .key_loader_interface import KeyLoaderInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["AbstractKeyLoader"]

# A value ending in one of these names a key file, never a key or a shared secret.
_KEY_FILE_SUFFIXES = frozenset({".pem", ".key"})

# What ``jwt:generate-keypair`` appends to a key id when it writes a JWK set.
_KEY_SET_SUFFIX = ".jwks.json"


class AbstractKeyLoader(  # pyright: ignore[reportImplicitAbstractClass]  -- RawKeyLoader implements load_key
    KeyLoaderInterface,
):
    """Reads a signing or verifying key from a raw string or a file path.

    The signing key and the public key may each be given either as the key text
    itself or as the path of a file holding it — an existing file wins, so a key
    that happens to look like a path is still read from disk when that path
    exists. The additional public keys, by contrast, must each be a readable
    file: they are the keys of other issuers a deployment trusts, kept on disk.
    Every key file is named after the key it holds, the way
    ``jwt:generate-keypair`` writes it, so the file's name is the id this loader
    reports the key under.

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
    def get_key_id(self) -> str | None:
        """Return the id the configured key files name this key pair by, if any.

        ``jwt:generate-keypair`` writes ``<kid>.pem``, so a deployment keeping
        its key in a file has already named the id there: the file's name without
        its suffix. A key given as text names no id, and a token's ``kid`` then
        matches it only when the key material itself carries one.
        """
        for value in (self._signing_key, self._public_key):
            file = _file_at(value)
            if file is not None:
                return _key_id_of(file)
        return None

    @override
    def get_additional_public_keys(self) -> Sequence[AdditionalPublicKey]:
        """Return the extra public keys, each read from its file under its name.

        Raises:
            InvalidArgumentError: When any configured path is not a readable file.
        """
        keys: list[AdditionalPublicKey] = []
        for path in self._additional_public_keys:
            file = Path(path)
            if not file.is_file():
                raise InvalidArgumentError(
                    f"The additional public key {path!r} is not a readable file.",
                )
            keys.append(AdditionalPublicKey(_key_id_of(file), file.read_text(encoding="utf-8")))
        return tuple(keys)

    @staticmethod
    def _read(value: str | None) -> str | None:
        """Return ``value`` itself, or the contents of the file it names.

        Raises:
            InvalidArgumentError: When ``value`` names a key file that does not
                exist. A missing ``.pem`` path would otherwise be handed on as key
                text and fail far away, as an unreadable-key error.
        """
        if value is None:
            return None
        file = _file_at(value)
        if file is not None:
            return file.read_text(encoding="utf-8")
        if "-----BEGIN" not in value and Path(value).suffix.lower() in _KEY_FILE_SUFFIXES:
            raise InvalidArgumentError(f"The key file {value!r} does not exist.")
        return value


def _file_at(value: str | None) -> Path | None:
    """Return the existing file ``value`` names, or ``None`` when it names none."""
    if value is None:
        return None
    path = Path(value)
    try:
        is_file = path.is_file()
    except OSError:
        # Older Pythons raise for a value too long to be a file name (inline key
        # text) instead of reporting it as not a file.
        return None
    return path if is_file else None


def _key_id_of(file: Path) -> str:
    """Return the key id ``file``'s name holds, its key suffix removed."""
    if file.name.endswith(_KEY_SET_SUFFIX):
        return file.name[: -len(_KEY_SET_SUFFIX)]
    return file.stem
