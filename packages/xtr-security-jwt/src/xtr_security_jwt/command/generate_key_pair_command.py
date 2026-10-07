"""``jwt:generate-keypair``: mint a signing key and print it as PEM and JWKS."""

from __future__ import annotations

import json
import os
import re
import secrets
from functools import partial
from pathlib import Path
from typing import Annotated, Final, Literal, final

import anyio.to_thread
from joserfc.jwk import ECKey, KeySet, OKPKey, RSAKey
from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.command._registry import JWT_COMMANDS

__all__ = ["GenerateKeyPairCommand"]

#: Everything a key identifier may be made of. The id names two files, so it is
#: held to an allow-list rather than to a list of the characters that would
#: escape the output directory — no separator, drive letter or stream name
#: survives it.
_SAFE_KID: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._-]+")

#: The mode the private PEM is written at: readable by its owner alone.
_PRIVATE_MODE: Final[int] = 0o600

#: The mode the public JWK set is written at: it is published, so it is readable.
_PUBLIC_MODE: Final[int] = 0o644

#: The mode every directory this command brings into being is left at.
_DIRECTORY_MODE: Final[int] = 0o700


@as_command("jwt:generate-keypair", registry=JWT_COMMANDS)
@final
class GenerateKeyPairCommand:
    """Mints a signing key and prints the private PEM and the public JWK set.

    Nothing is written to disk unless ``--output-dir`` is given, so the keys can
    be piped into a secret store. With it, the private PEM and the public JWKS are
    written there, named by the key's identifier — never over a key file already
    in place unless ``--force`` says so, and never through a symbolic link
    planted where a key file is about to land.
    """

    __slots__ = ()

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        algorithm: Annotated[
            Literal["RS256", "ES256", "EdDSA"],
            Option(help="The signature algorithm the key is for."),
        ] = "RS256",
        kid: Annotated[
            str | None,
            Option(help="The key identifier; a random one when omitted."),
        ] = None,
        output_dir: Annotated[
            str | None,
            Option(help="A directory to write the PEM and JWKS into, instead of printing them."),
        ] = None,
        force: Annotated[
            bool,
            Option(help="Replace a key file already in the output directory."),
        ] = False,
    ) -> int:
        """Mint the key and print or write its private PEM and public JWKS."""
        key_id = kid if kid is not None else secrets.token_hex(8)
        _require_safe_kid(key_id)
        key = _generate(algorithm, key_id)
        private_pem = key.as_pem(private=True).decode()
        public_jwks = json.dumps(KeySet([key]).as_dict(private=False), indent=2)

        if output_dir is not None:
            private_path, public_path = await _write_key_files(
                Path(output_dir),
                key_id,
                private_pem,
                public_jwks,
                force=force,
            )
            io.success(f"Wrote {escape(str(private_path))} and {escape(str(public_path))}.")
            return ExitCode.SUCCESS

        io.title("JWT key pair")
        io.text(f"Algorithm: {escape(algorithm)}")
        io.text(f"Key id: {escape(key_id)}")
        io.section("Private key (PEM)")
        io.text(escape(private_pem))
        io.section("Public key set (JWKS)")
        io.text(escape(public_jwks))
        return ExitCode.SUCCESS


def _require_safe_kid(key_id: str) -> None:
    """Refuse a key id that is not plainly a file name of its own.

    The id names ``<kid>.pem`` and ``<kid>.jwks.json``, so only letters, digits,
    dots, dashes and underscores pass — a separator, a drive letter, a stream
    name or a ``..`` is refused rather than resolved.

    Raises:
        InvalidArgumentError: When the key id is empty, holds a character outside
            the allow-list, or walks up with ``..``.
    """
    if _SAFE_KID.fullmatch(key_id) is None or ".." in key_id:
        raise InvalidArgumentError(
            "A key id is made of letters, digits, '.', '-' and '_' alone, and never walks "
            f"up with '..'; {key_id!r} would not stay inside the output directory.",
        )


async def _write_key_files(
    directory: Path,
    key_id: str,
    private_pem: str,
    public_jwks: str,
    *,
    force: bool,
) -> tuple[Path, Path]:
    """Write the PEM and the JWKS into ``directory``, the blocking work off the loop.

    Returns:
        The paths the private PEM and the public JWK set were written to.
    """
    private_path = directory / f"{key_id}.pem"
    public_path = directory / f"{key_id}.jwks.json"
    await anyio.to_thread.run_sync(
        partial(
            _write_key_pair,
            private_path,
            private_pem,
            public_path,
            public_jwks,
            force=force,
        ),
    )
    return private_path, public_path


def _write_key_pair(
    private_path: Path,
    private_pem: str,
    public_path: Path,
    public_jwks: str,
    *,
    force: bool,
) -> None:
    """Create the output directory privately and write the two key files.

    The private PEM goes through a descriptor opened ``0o600``, its mode set
    before any byte reaches it, so a signing key never sits world-readable even
    briefly; the JWK set is published, so it is written ``0o644``.

    A signing key never outlives the JWK set a verifier needs to accept it, so
    a refused or failed set takes the PEM this call just wrote with it: the
    command reports nothing written, and nothing stays written.
    """
    _create_private_directory(private_path.parent)
    _write_file(private_path, private_pem, _PRIVATE_MODE, force=force)
    try:
        _write_file(public_path, public_jwks, _PUBLIC_MODE, force=force)
    except BaseException:
        private_path.unlink(missing_ok=True)
        raise


def _write_file(path: Path, text: str, mode: int, *, force: bool) -> None:
    """Write ``text`` into ``path`` at ``mode``, never through a symbolic link.

    The descriptor is opened ``O_NOFOLLOW``, so a link planted where a key file
    is about to land cannot redirect the write to whatever it points at, and
    ``O_EXCL`` keeps a key already in place from being replaced by accident.
    ``force`` trades the exclusive create for a truncating write, which still
    refuses to follow a link.

    Raises:
        InvalidArgumentError: When the path cannot be opened as a regular file
            this call may write — something is already there, or it is a link or
            a directory.
    """
    replace = os.O_TRUNC if force else os.O_EXCL
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | replace | os.O_NOFOLLOW, mode)
    except FileExistsError as error:
        raise InvalidArgumentError(
            f"{path} is already there; pass --force to replace a key file in place.",
        ) from error
    except OSError as error:
        raise InvalidArgumentError(
            f"{path} could not be opened as a regular file to write ({error}); a key is "
            "never written through a symbolic link.",
        ) from error
    try:
        os.fchmod(descriptor, mode)
        _ = os.write(descriptor, text.encode("utf-8"))
    finally:
        os.close(descriptor)


def _create_private_directory(directory: Path) -> None:
    """Create ``directory`` and every missing parent, each left owner-only (``0o700``).

    ``mkdir``'s mode is narrowed by the process umask, so each directory this
    call brings into being has its mode set afterwards — through a descriptor
    that refuses to follow a link, so a directory swapped for a symbolic link
    between the two steps cannot redirect the change. A directory that already
    existed is left exactly as it is: its mode is the deployment's to choose, not
    this command's to tighten.
    """
    for one in reversed([directory, *directory.parents]):
        if one.exists():
            continue
        try:
            one.mkdir(mode=_DIRECTORY_MODE)
        except FileExistsError:  # another writer won the race, and owns the mode
            continue
        _make_directory_private(one)


def _make_directory_private(directory: Path) -> None:
    """Set ``directory`` owner-only through a descriptor that refuses to follow a link."""
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(descriptor, _DIRECTORY_MODE)
    finally:
        os.close(descriptor)


def _generate(algorithm: str, key_id: str) -> RSAKey | ECKey | OKPKey:
    """Mint a key of the type ``algorithm`` demands, carrying ``key_id``."""
    if algorithm == "RS256":
        return RSAKey.generate_key(2048, parameters={"kid": key_id})
    if algorithm == "ES256":
        return ECKey.generate_key("P-256", parameters={"kid": key_id})
    return OKPKey.generate_key("Ed25519", parameters={"kid": key_id})
