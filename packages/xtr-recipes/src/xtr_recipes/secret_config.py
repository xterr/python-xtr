"""SecretConfig: a secret a recipe asks the sync to make up for ``.env``."""

from __future__ import annotations

import base64
import re
import secrets
from dataclasses import dataclass
from typing import Final, final

from .exception import InvalidManifestError

__all__ = ["DEFAULT_BYTES", "ENCODINGS", "MAX_BYTES", "MIN_BYTES", "SecretConfig"]

DEFAULT_BYTES: Final = 32
"""How many random bytes a secret carries unless told: 256 bits, enough for a key."""

MIN_BYTES: Final = 16
"""The fewest random bytes a secret may carry: 128 bits, below which it is guessable."""

MAX_BYTES: Final = 1024
"""The most random bytes a secret may carry."""

ENCODINGS: Final = ("base64url", "base64", "hex")
"""How a secret's bytes may be spelled.

``base64url`` — the default — is unpadded and safe unquoted in ``.env`` and in a URL;
``base64`` is the standard alphabet with its padding, which a ``whsec_`` secret uses;
``hex`` is lower-case hexadecimal.
"""

# What every generator placeholder opens with; a value that does not is a plain default.
_OPENING = "%generate("
_PLACEHOLDER = re.compile(r"%generate\((?P<kind>\w+)(?P<arguments>(?:\s*,[^()%]*)?)\)%")
_ARGUMENT = re.compile(r"\s*(?P<name>\w+)\s*=\s*(?P<value>[^\s,]*)\s*")
_PREFIX = re.compile(r"[A-Za-z0-9_.:-]+")
_KIND = "secret"
_NAMES = frozenset({"bytes", "encoding", "prefix"})


@final
@dataclass(frozen=True, slots=True)
class SecretConfig:
    """How one generated secret is made: how many random bytes, spelled how.

    Written in an ``[env]`` default as ``%generate(secret)%``, optionally followed
    by keyword arguments — ``%generate(secret, bytes=64, encoding=hex)%``,
    ``%generate(secret, encoding=base64, prefix=whsec_)%`` — and read by
    :meth:`parse`, which is where a manifest's spelling is checked.

    Attributes:
        byte_count: How many random bytes the secret carries, from
            :data:`MIN_BYTES` to :data:`MAX_BYTES`.
        encoding: How those bytes are spelled, one of :data:`ENCODINGS`.
        prefix: Text written before them, for a format that marks its secrets.
    """

    byte_count: int = DEFAULT_BYTES
    encoding: str = "base64url"
    prefix: str = ""

    @classmethod
    def parse(cls, package: str, key: str, value: str) -> SecretConfig | None:
        """Read the generator ``value`` spells, or ``None`` when it is a plain default.

        Args:
            package: The distribution whose manifest this is, named in errors.
            key: The ``[env]`` key the value is the default of, named in errors.
            value: The default as the manifest writes it.

        Returns:
            How the secret is made, or ``None`` when ``value`` is no generator.

        Raises:
            InvalidManifestError: When ``value`` opens a generator and does not
                spell one: an unknown kind, an unknown or repeated argument, a
                size out of range, an unknown encoding or an unsafe prefix. A
                misspelt generator would otherwise reach ``.env`` as a literal,
                and the application would read the placeholder as its secret.
        """
        if not value.startswith(_OPENING):
            return None
        where = f"env.{key}"
        matched = _PLACEHOLDER.fullmatch(value)
        if matched is None:
            raise InvalidManifestError(package, where, "expected %generate(secret, name=value, …)%")
        if matched["kind"] != _KIND:
            raise InvalidManifestError(package, where, f"unknown generator {matched['kind']!r}")
        arguments = _arguments(package, where, matched["arguments"])
        return cls(
            byte_count=_byte_count(package, where, arguments.get("bytes")),
            encoding=_encoding(package, where, arguments.get("encoding")),
            prefix=_prefix(package, where, arguments.get("prefix")),
        )

    def generate(self) -> str:
        """Return a fresh secret: the prefix, then :attr:`byte_count` random bytes encoded."""
        raw = secrets.token_bytes(self.byte_count)
        if self.encoding == "hex":
            body = raw.hex()
        elif self.encoding == "base64":
            body = base64.b64encode(raw).decode("ascii")
        else:
            body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        return f"{self.prefix}{body}"


def _arguments(package: str, where: str, text: str) -> dict[str, str]:
    """Return the ``name=value`` arguments after the generator's kind, each named once."""
    arguments: dict[str, str] = {}
    for part in text.split(",")[1:]:
        matched = _ARGUMENT.fullmatch(part)
        if matched is None:
            raise InvalidManifestError(package, where, f"expected name=value, got {part.strip()!r}")
        name = matched["name"]
        if name not in _NAMES:
            raise InvalidManifestError(package, where, f"unknown argument {name!r}")
        if name in arguments:
            raise InvalidManifestError(package, where, f"argument {name!r} given twice")
        arguments[name] = matched["value"]
    return arguments


def _byte_count(package: str, where: str, value: str | None) -> int:
    """Return the byte count asked for, refusing one that is not a number in range."""
    if value is None:
        return DEFAULT_BYTES
    if not value.isdigit() or not MIN_BYTES <= int(value) <= MAX_BYTES:
        raise InvalidManifestError(
            package, where, f"bytes must be a whole number from {MIN_BYTES} to {MAX_BYTES}"
        )
    return int(value)


def _encoding(package: str, where: str, value: str | None) -> str:
    """Return the encoding asked for, refusing one this generator cannot write."""
    if value is None:
        return ENCODINGS[0]
    if value not in ENCODINGS:
        raise InvalidManifestError(
            package, where, f"encoding must be one of {', '.join(ENCODINGS)}"
        )
    return value


def _prefix(package: str, where: str, value: str | None) -> str:
    """Return the prefix asked for, refusing one that would need quoting in ``.env``."""
    if value is None:
        return ""
    if _PREFIX.fullmatch(value) is None:
        raise InvalidManifestError(
            package, where, "prefix may hold only letters, digits and _ . : -"
        )
    return value
