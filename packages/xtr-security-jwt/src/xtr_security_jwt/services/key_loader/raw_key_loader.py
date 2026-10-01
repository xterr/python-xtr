"""A key loader that also derives the public key from the private one."""

from __future__ import annotations

from typing import ClassVar, final

from joserfc.errors import JoseError
from joserfc.jwk import ECKey, OKPKey, RSAKey
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .abstract_key_loader import AbstractKeyLoader
from .key_dumper_interface import KeyDumperInterface
from .key_loader_interface import TYPE_PUBLIC

__all__ = ["RawKeyLoader"]

_ASYMMETRIC_KEY_CLASSES: tuple[type[RSAKey | ECKey | OKPKey], ...] = (
    RSAKey,
    ECKey,
    OKPKey,
)


@final
class RawKeyLoader(AbstractKeyLoader, KeyDumperInterface):
    """Loads keys from raw text or files, and derives a public key when it is absent.

    :meth:`load_key` hands the private key for signing and the public key for
    verifying; when no public key was configured, it is derived from the private
    key, so a deployment can configure a single private key and still publish
    the matching public one.
    """

    __slots__: ClassVar[tuple[str, ...]] = ()

    @override
    def load_key(self, key_type: str) -> str:
        """Return the private or public key text.

        Raises:
            InvalidArgumentError: When the requested key is not available.
        """
        if key_type == TYPE_PUBLIC:
            return self.dump_key()
        signing_key = self.get_signing_key()
        if signing_key is None:
            raise InvalidArgumentError("This key loader holds no signing key.")
        return signing_key

    @override
    def dump_key(self) -> str:
        """Return the public key text, deriving it from the private key when unset.

        Raises:
            InvalidArgumentError: When neither a public key nor a private key to
                derive one from is available, or the private key cannot be read.
        """
        public_key = self.get_public_key()
        if public_key is not None:
            return public_key
        signing_key = self.get_signing_key()
        if signing_key is None:
            raise InvalidArgumentError(
                "This key loader has neither a public key nor a private key to derive one from.",
            )
        return _public_pem_from_private(signing_key, self.get_passphrase())


def _public_pem_from_private(private_pem: str, passphrase: str | None) -> str:
    """Derive the public PEM from a private PEM, trying each asymmetric key type.

    Raises:
        InvalidArgumentError: When the private key cannot be read as any
            supported asymmetric key.
    """
    password = passphrase.encode("utf-8") if passphrase else None
    for key_class in _ASYMMETRIC_KEY_CLASSES:
        try:
            key = key_class.import_key(private_pem, password=password)
        except (JoseError, ValueError, TypeError):
            continue
        return key.as_pem(private=False).decode("utf-8")
    raise InvalidArgumentError("The private key could not be read to derive a public key.")
