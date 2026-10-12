"""``oauth2-server:generate-keypair``: mint the key this server signs access tokens with."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Annotated, Final, final

import anyio.to_thread
from xtr_console import Argument, ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_security_jwt.services.key_loader import generate_signing_key
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

from ._key_files import PRIVATE_MODE, PUBLIC_MODE, write_key_file
from ._key_paths import private_key_path, public_key_path
from ._registry import OAUTH2_SERVER_COMMANDS

if TYPE_CHECKING:
    from pathlib import Path

    from joserfc.jwk import ECKey, OKPKey, RSAKey

__all__ = ["ALGORITHMS", "GenerateKeyPairCommand"]

ALGORITHMS: Final = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)
"""Every algorithm a key pair can be minted for.

The shared-secret algorithms are absent on purpose: there is no pair to mint
for one, only a secret a deployment chooses and configures.
"""


@as_command("oauth2-server:generate-keypair", registry=OAUTH2_SERVER_COMMANDS)
@final
class GenerateKeyPairCommand:
    """Mints a signing key pair and writes it where this deployment reads it.

    The paths are not this command's to choose: it writes the file
    ``authorization_server.private_key`` names, and the file
    ``resource_server.public_key`` names when the deployment named one — a
    verifying key is otherwise derived from the private one, so there is
    nothing to write for it.

    A key file in place is never replaced by accident: ``--overwrite`` is what
    allows it and confirms it, ``--skip-if-exists`` leaves it alone, and
    ``--dry-run`` writes nothing at all, so the pair can be read off the
    terminal and put into a secret store instead.
    """

    __slots__ = ("_algorithm", "_passphrase", "_private_key", "_public_key")

    def __init__(
        self,
        private_key: str,
        public_key: str,
        passphrase: str,
        algorithm: str,
    ) -> None:
        """Mint for ``algorithm`` and write where ``private_key`` and ``public_key`` point.

        Args:
            private_key: What ``authorization_server.private_key`` holds — the
                path of the file the signing key is read from, or the key text
                itself, in which case there is no file to write.
            public_key: What ``resource_server.public_key`` holds, or empty
                when the verifying key is derived from the signing one.
            passphrase: What the private key is encrypted with as it is
                written, or empty for none.
            algorithm: The algorithm this deployment signs with, which is what
                a run naming none mints for.
        """
        self._private_key = private_key
        self._public_key = public_key
        self._passphrase = passphrase
        self._algorithm = algorithm

    async def __call__(
        self,
        io: ConsoleStyle,
        algorithm: Annotated[
            str | None,
            Argument(help="The algorithm to mint for; the configured one when left out."),
        ] = None,
        *,
        dry_run: Annotated[bool, Option(help="Print the pair instead of writing it.")] = False,
        skip_if_exists: Annotated[
            bool,
            Option(help="Leave the key files alone when they are already there."),
        ] = False,
        overwrite: Annotated[
            bool,
            Option(help="Replace the key files when they are already there."),
        ] = False,
    ) -> int:
        """Mint the signing key pair, and write it where the configuration points."""
        chosen = algorithm if algorithm is not None else self._algorithm
        if chosen not in ALGORITHMS:
            io.error(
                f"Cannot generate a key pair with the algorithm {escape(chosen)}; the "
                f"algorithms a pair is minted for are {', '.join(ALGORITHMS)}.",
            )

            return ExitCode.FAILURE
        try:
            private_path = private_key_path(self._private_key)
            public_path = public_key_path(self._public_key)
        except InvalidConfigurationError as error:
            io.error(escape(str(error)))

            return ExitCode.FAILURE
        key = generate_signing_key(chosen)
        private_pem = _private_pem(key, self._passphrase)
        public_pem = key.as_pem(private=False).decode("utf-8")
        if dry_run:
            _printed(io, private_path, private_pem, public_path, public_pem)

            return ExitCode.SUCCESS

        return await _written(
            io,
            (private_path, private_pem),
            (public_path, public_pem),
            skip_if_exists=skip_if_exists,
            overwrite=overwrite,
        )


def _private_pem(key: RSAKey | ECKey | OKPKey, passphrase: str) -> str:
    """Return the private PEM, encrypted with ``passphrase`` when there is one."""
    return key.as_pem(private=True, password=passphrase or None).decode("utf-8")


def _printed(
    io: ConsoleStyle,
    private_path: Path,
    private_pem: str,
    public_path: Path | None,
    public_pem: str,
) -> None:
    """Show the minted pair and where each half belongs, having written nothing."""
    io.success("Your keys have been generated!")
    io.section(f"Private key — write it to {escape(str(private_path))}")
    io.text(escape(private_pem))
    where = (
        f"write it to {escape(str(public_path))}"
        if public_path is not None
        else "derived from the private key, so no file holds it"
    )
    io.section(f"Public key — {where}")
    io.text(escape(public_pem))


async def _written(
    io: ConsoleStyle,
    private: tuple[Path, str],
    public: tuple[Path | None, str],
    *,
    skip_if_exists: bool,
    overwrite: bool,
) -> int:
    """Write the pair, unless a file in place says not to, and report what happened."""
    private_path, private_pem = private
    public_path, public_pem = public
    in_place = [path for path in (private_path, public_path) if path is not None and path.exists()]
    if in_place:
        refused = _refusal(skip_if_exists=skip_if_exists, overwrite=overwrite)
        if refused is not None:
            message, code = refused
            if code == ExitCode.SUCCESS:
                io.note(message)
            else:
                io.error(message)

            return code
        if not io.confirm(
            "You are about to replace your existing keys. Are you sure you wish to continue?",
            default=True,
        ):
            io.note("Your action was canceled.")

            return ExitCode.SUCCESS
    written = [(private_path, private_pem, PRIVATE_MODE)]
    if public_path is not None:
        written.append((public_path, public_pem, PUBLIC_MODE))
    try:
        for path, text, mode in written:
            await anyio.to_thread.run_sync(partial(write_key_file, path, text, mode))
    except InvalidArgumentError as error:
        io.error(escape(str(error)))

        return ExitCode.FAILURE
    io.success("Done!")
    io.listing([escape(str(path)) for path, _text, _mode in written])

    return ExitCode.SUCCESS


def _refusal(*, skip_if_exists: bool, overwrite: bool) -> tuple[str, int] | None:
    """Return why the key files in place are left alone, and with which exit code.

    ``None`` means they may be replaced, once whoever asked has confirmed it.
    """
    if skip_if_exists and overwrite:
        return (
            "Both options `--skip-if-exists` and `--overwrite` cannot be combined.",
            ExitCode.FAILURE,
        )
    if skip_if_exists:
        return ("Your key files already exist, they won't be overridden.", ExitCode.SUCCESS)
    if not overwrite:
        return (
            "Your keys already exist. Use the `--overwrite` option to force regeneration.",
            ExitCode.FAILURE,
        )

    return None
