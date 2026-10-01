"""``jwt:generate-keypair`` prints or writes a signing key."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from xtr_console import ConsoleStyle

from xtr_security_jwt.command.generate_key_pair_command import GenerateKeyPairCommand

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


def _style() -> tuple[ConsoleStyle, io.StringIO]:
    output = io.StringIO()
    style = ConsoleStyle(output, io.StringIO(), width=200, decorated=False, interactive=False)
    return style, output


async def test_it_prints_a_private_pem_and_public_jwks() -> None:
    style, output = _style()

    code = await GenerateKeyPairCommand()(style)

    assert code == 0
    printed = output.getvalue()
    assert "BEGIN PRIVATE KEY" in printed
    assert '"keys"' in printed


async def test_it_honours_the_key_id() -> None:
    style, output = _style()

    code = await GenerateKeyPairCommand()(style, kid="chosen-kid")

    assert code == 0
    assert "chosen-kid" in output.getvalue()


async def test_an_ec_key_is_minted() -> None:
    style, output = _style()

    code = await GenerateKeyPairCommand()(style, algorithm="ES256")

    assert code == 0
    assert "ES256" in output.getvalue()


async def test_it_writes_the_files_to_a_directory(tmp_path: Path) -> None:
    style, _ = _style()

    code = await GenerateKeyPairCommand()(style, kid="written", output_dir=str(tmp_path))

    assert code == 0
    assert (tmp_path / "written.pem").read_text().startswith("-----BEGIN")
    assert '"keys"' in (tmp_path / "written.jwks.json").read_text()
