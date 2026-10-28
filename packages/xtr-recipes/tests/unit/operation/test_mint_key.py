from __future__ import annotations

import stat
from typing import TYPE_CHECKING

from xtr_recipes.operation.mint_key import MintKey

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_the_path_and_algorithm_never_the_key(tmp_path: Path) -> None:
    step = MintKey(tmp_path / "server.pem", "secrets/server.pem", "RS256", "secret")

    assert step.render() == ("  mint secrets/server.pem (RS256)",)


def test_it_counts_as_a_change() -> None:
    assert MintKey.changes is True


def test_it_writes_a_key_the_owner_alone_can_read(tmp_path: Path) -> None:
    path = tmp_path / "secrets" / "server.pem"

    MintKey(path, "secrets/server.pem", "EdDSA").apply()

    assert path.read_text(encoding="utf-8").startswith("-----BEGIN PRIVATE KEY-----")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_it_encrypts_the_key_with_its_passphrase(tmp_path: Path) -> None:
    path = tmp_path / "server.pem"

    MintKey(path, "server.pem", "ES256", "secret").apply()

    assert path.read_text(encoding="utf-8").startswith("-----BEGIN ENCRYPTED PRIVATE KEY-----")


def test_it_never_replaces_a_key_already_there(tmp_path: Path) -> None:
    path = tmp_path / "server.pem"
    _ = path.write_text("MINE\n", encoding="utf-8")

    MintKey(path, "server.pem", "RS256").apply()

    assert path.read_text(encoding="utf-8") == "MINE\n"
