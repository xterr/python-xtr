"""``jwt:generate-keypair`` prints or writes a signing key."""

from __future__ import annotations

import io
import stat
from typing import TYPE_CHECKING

import pytest
from xtr_console import ConsoleStyle
from xtr_security_core.exception import InvalidArgumentError

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


async def test_the_written_private_key_is_owner_only(tmp_path: Path) -> None:
    style, _ = _style()

    _ = await GenerateKeyPairCommand()(style, kid="private", output_dir=str(tmp_path))

    mode = stat.S_IMODE((tmp_path / "private.pem").stat().st_mode)
    assert mode == 0o600


async def test_the_output_directory_is_created_owner_only(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "secrets"

    _ = await GenerateKeyPairCommand()(style, kid="k", output_dir=str(target))

    assert stat.S_IMODE(target.stat().st_mode) == 0o700


async def test_every_directory_it_creates_is_owner_only(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "var" / "secrets" / "jwt"

    _ = await GenerateKeyPairCommand()(style, kid="k", output_dir=str(target))

    created = (tmp_path / "var", tmp_path / "var" / "secrets", target)
    assert [stat.S_IMODE(one.stat().st_mode) for one in created] == [0o700, 0o700, 0o700]


async def test_a_directory_that_already_exists_keeps_its_mode(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "shared"
    target.mkdir(mode=0o755)
    target.chmod(0o755)

    _ = await GenerateKeyPairCommand()(style, kid="k", output_dir=str(target))

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


async def test_a_kid_that_escapes_the_directory_is_refused(tmp_path: Path) -> None:
    style, _ = _style()

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="../x", output_dir=str(tmp_path))


async def test_a_kid_with_a_separator_is_refused() -> None:
    style, _ = _style()

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="a/b")


async def test_a_kid_with_a_colon_is_refused() -> None:
    style, _ = _style()

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="C:name")


async def test_a_kid_with_a_space_is_refused() -> None:
    style, _ = _style()

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="a b")


async def test_the_written_public_jwks_is_world_readable(tmp_path: Path) -> None:
    style, _ = _style()

    _ = await GenerateKeyPairCommand()(style, kid="public", output_dir=str(tmp_path))

    mode = stat.S_IMODE((tmp_path / "public.jwks.json").stat().st_mode)
    assert mode == 0o644


async def test_a_private_key_is_never_written_through_a_planted_symlink(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "target.pem"
    _ = target.write_text("untouched", encoding="utf-8")
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "planted.pem").symlink_to(target)

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="planted", output_dir=str(directory))

    assert target.read_text(encoding="utf-8") == "untouched"


async def test_force_does_not_follow_a_planted_symlink_either(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "target.pem"
    _ = target.write_text("untouched", encoding="utf-8")
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "planted.pem").symlink_to(target)

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(
            style,
            kid="planted",
            output_dir=str(directory),
            force=True,
        )

    assert target.read_text(encoding="utf-8") == "untouched"


async def test_a_jwks_is_never_written_through_a_planted_symlink(tmp_path: Path) -> None:
    style, _ = _style()
    target = tmp_path / "target.json"
    _ = target.write_text("untouched", encoding="utf-8")
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "planted.jwks.json").symlink_to(target)

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="planted", output_dir=str(directory))

    assert target.read_text(encoding="utf-8") == "untouched"


async def test_a_jwks_that_cannot_be_written_leaves_no_private_key_behind(
    tmp_path: Path,
) -> None:
    """The PEM was written first, so a refused JWK set left a signing key on
    disk that the command reported as never written."""
    style, _ = _style()
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "planted.jwks.json").symlink_to(tmp_path / "target.json")

    with pytest.raises(InvalidArgumentError):
        _ = await GenerateKeyPairCommand()(style, kid="planted", output_dir=str(directory))

    assert not (directory / "planted.pem").exists()


async def test_an_existing_key_file_is_not_overwritten_without_force(tmp_path: Path) -> None:
    style, _ = _style()
    existing = tmp_path / "taken.pem"
    _ = existing.write_text("the key in use", encoding="utf-8")

    with pytest.raises(InvalidArgumentError, match="--force"):
        _ = await GenerateKeyPairCommand()(style, kid="taken", output_dir=str(tmp_path))

    assert existing.read_text(encoding="utf-8") == "the key in use"


async def test_force_replaces_an_existing_key_file(tmp_path: Path) -> None:
    style, _ = _style()
    existing = tmp_path / "taken.pem"
    _ = existing.write_text("the key in use", encoding="utf-8")

    code = await GenerateKeyPairCommand()(
        style,
        kid="taken",
        output_dir=str(tmp_path),
        force=True,
    )

    assert code == 0
    assert existing.read_text(encoding="utf-8").startswith("-----BEGIN")
    assert stat.S_IMODE(existing.stat().st_mode) == 0o600
