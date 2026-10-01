"""``jwt:generate-keypair``: mint a signing key and print it as PEM and JWKS."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Annotated, Literal, final

from joserfc.jwk import ECKey, KeySet, OKPKey, RSAKey
from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape

from xtr_security_jwt.command._registry import JWT_COMMANDS

__all__ = ["GenerateKeyPairCommand"]


@as_command("jwt:generate-keypair", registry=JWT_COMMANDS)
@final
class GenerateKeyPairCommand:
    """Mints a signing key and prints the private PEM and the public JWK set.

    Nothing is written to disk unless ``--output-dir`` is given, so the keys can
    be piped into a secret store. With it, the private PEM and the public JWKS are
    written there, named by the key's identifier.
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
    ) -> int:
        """Mint the key and print or write its private PEM and public JWKS."""
        key_id = kid or secrets.token_hex(8)
        key = _generate(algorithm, key_id)
        private_pem = key.as_pem(private=True).decode()
        public_jwks = json.dumps(KeySet([key]).as_dict(private=False), indent=2)

        if output_dir is not None:
            return self._write(io, output_dir, key_id, private_pem, public_jwks)

        io.title("JWT key pair")
        io.text(f"Algorithm: {escape(algorithm)}")
        io.text(f"Key id: {escape(key_id)}")
        io.section("Private key (PEM)")
        io.text(escape(private_pem))
        io.section("Public key set (JWKS)")
        io.text(escape(public_jwks))
        return ExitCode.SUCCESS

    def _write(
        self,
        io: ConsoleStyle,
        output_dir: str,
        key_id: str,
        private_pem: str,
        public_jwks: str,
    ) -> int:
        """Write the PEM and JWKS into ``output_dir``, named by the key id."""
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        private_path = directory / f"{key_id}.pem"
        public_path = directory / f"{key_id}.jwks.json"
        _ = private_path.write_text(private_pem, encoding="utf-8")
        _ = public_path.write_text(public_jwks, encoding="utf-8")
        io.success(f"Wrote {escape(str(private_path))} and {escape(str(public_path))}.")
        return ExitCode.SUCCESS


def _generate(algorithm: str, key_id: str) -> RSAKey | ECKey | OKPKey:
    """Mint a key of the type ``algorithm`` demands, carrying ``key_id``."""
    if algorithm == "RS256":
        return RSAKey.generate_key(2048, parameters={"kid": key_id})
    if algorithm == "ES256":
        return ECKey.generate_key("P-256", parameters={"kid": key_id})
    return OKPKey.generate_key("Ed25519", parameters={"kid": key_id})
