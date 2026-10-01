"""The crypto layers import none of the HTTP edge they sit beneath."""

from __future__ import annotations

import subprocess
import sys

#: The HTTP edge the signing and verification layers must stay clear of.
FORBIDDEN = (
    "fastapi",
    "starlette",
    "xtr_security_http",
)

#: The crypto layers — signing, verification and their value objects — that an
#: application may import without dragging in the HTTP edge.
CRYPTO_LAYERS = (
    "xtr_security_jwt.encoder.default_jwt_encoder",
    "xtr_security_jwt.services.jwt_manager",
    "xtr_security_jwt.services.jws_provider.joserfc_jws_provider",
    "xtr_security_jwt.services.key_loader.raw_key_loader",
    "xtr_security_jwt.signature.created_jws",
    "xtr_security_jwt.signature.loaded_jws",
)


def test_importing_the_crypto_layers_stays_clear_of_the_http_edge() -> None:
    program = (
        "import sys\n"
        f"for module in {CRYPTO_LAYERS!r}:\n"
        "    __import__(module)\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "leaked = sorted(name for name in forbidden if name in sys.modules)\n"
        "print(','.join(leaked))\n"
    )

    result = subprocess.run(  # noqa: S603 — a fixed program on this interpreter, no untrusted input
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == ""
