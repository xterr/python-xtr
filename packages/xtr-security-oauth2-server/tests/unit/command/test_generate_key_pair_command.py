"""``oauth2-server:generate-keypair`` mints the key this server signs with."""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING, Final

import pytest
from joserfc.jwk import ECKey, RSAKey
from xtr_console import CommandTester, ExitCode

from tests.fixtures.oauth2_keypair_app.config import (
    ALGORITHM,
    PASSPHRASE,
    PRIVATE_KEY_VARIABLE,
    PUBLIC_KEY_VARIABLE,
)
from tests.support.console import IN_MEMORY_APP, console_kernel, running
from tests.support.signing import SIGNING_KEY_PEM

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from pathlib import Path

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:generate-keypair"

#: The deployment naming both halves of its key pair, as a split one does.
_BOTH_HALVES_APP: Final = "tests.fixtures.oauth2_keypair_app"

#: The deployment naming only the signing key, as nearly every one does.
_SIGNING_KEY_ONLY_APP: Final = "tests.fixtures.oauth2_env_app"

#: The deployment that configured nothing at all.
_UNCONFIGURED_APP: Final = "tests.fixtures.oauth2_unconfigured_app"

#: What a key file holds before a run, so a refusal can be seen to leave it alone.
_IN_PLACE: Final = "the key in use"


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    """Return where the private and the public halves belong."""
    return tmp_path / "secrets" / "oauth2.pem", tmp_path / "secrets" / "oauth2.pub.pem"


def _environ(tmp_path: Path) -> Mapping[str, str]:
    """Return the environment naming both halves of the key pair."""
    private_path, public_path = _paths(tmp_path)

    return {PRIVATE_KEY_VARIABLE: str(private_path), PUBLIC_KEY_VARIABLE: str(public_path)}


@pytest.fixture
async def console(tmp_path: Path) -> AsyncIterator[CommandTester]:
    """Hand over the command of a deployment naming both halves of its pair."""
    async with running(
        console_kernel(_BOTH_HALVES_APP, environ=_environ(tmp_path)),
    ) as (application, _container):
        yield CommandTester(application, _COMMAND, width=200)


async def test_it_writes_both_halves_where_the_configuration_points(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, public_path = _paths(tmp_path)

    code = await console.execute()

    assert code == ExitCode.SUCCESS
    assert "Done!" in console.display
    assert "PRIVATE KEY" in private_path.read_text(encoding="utf-8")
    assert "PUBLIC KEY" in public_path.read_text(encoding="utf-8")
    assert str(private_path) in console.display
    assert str(public_path) in console.display


async def test_the_private_half_is_readable_by_its_owner_alone(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, public_path = _paths(tmp_path)

    assert await console.execute() == ExitCode.SUCCESS

    assert stat.S_IMODE(private_path.stat().st_mode) == 0o600
    # The public half is published, so it is readable.
    assert stat.S_IMODE(public_path.stat().st_mode) == 0o644


async def test_the_private_half_is_encrypted_with_the_configured_pass_phrase(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)

    assert await console.execute() == ExitCode.SUCCESS

    pem = private_path.read_text(encoding="utf-8")
    assert "ENCRYPTED PRIVATE KEY" in pem
    assert ECKey.import_key(pem, password=PASSPHRASE.encode()) is not None


async def test_a_run_naming_no_algorithm_mints_for_the_configured_one(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)

    assert await console.execute() == ExitCode.SUCCESS

    minted = ECKey.import_key(
        private_path.read_text(encoding="utf-8"),
        password=PASSPHRASE.encode(),
    )
    assert minted.key_type == "EC"
    assert ALGORITHM == "ES256"


async def test_an_algorithm_named_on_the_command_line_is_the_one_minted_for(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)

    assert await console.execute(["RS256"]) == ExitCode.SUCCESS

    minted = RSAKey.import_key(
        private_path.read_text(encoding="utf-8"),
        password=PASSPHRASE.encode(),
    )
    assert minted.key_type == "RSA"


async def test_an_algorithm_no_pair_can_be_minted_for_is_refused(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)

    code = await console.execute(["HS256"])

    assert code == ExitCode.FAILURE
    assert "Cannot generate a key pair with the algorithm HS256" in console.display
    assert not private_path.exists()


async def test_a_dry_run_shows_the_pair_and_writes_nothing(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, public_path = _paths(tmp_path)

    code = await console.execute(["--dry-run"])

    assert code == ExitCode.SUCCESS
    assert "Your keys have been generated!" in console.display
    assert "PRIVATE KEY" in console.display
    assert "PUBLIC KEY" in console.display
    assert not private_path.exists()
    assert not public_path.exists()


async def _in_place(tmp_path: Path) -> tuple[Path, Path]:
    """Put a key file where each half belongs, and return the two paths."""
    private_path, public_path = _paths(tmp_path)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    _ = private_path.write_text(_IN_PLACE, encoding="utf-8")
    _ = public_path.write_text(_IN_PLACE, encoding="utf-8")

    return private_path, public_path


async def test_keys_already_in_place_are_not_replaced_without_being_asked(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, public_path = await _in_place(tmp_path)

    code = await console.execute()

    assert code == ExitCode.FAILURE
    assert "Use the `--overwrite` option to force regeneration." in console.display
    assert private_path.read_text(encoding="utf-8") == _IN_PLACE
    assert public_path.read_text(encoding="utf-8") == _IN_PLACE


async def test_skipping_leaves_keys_already_in_place_exactly_as_they_were(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = await _in_place(tmp_path)

    code = await console.execute(["--skip-if-exists"])

    assert code == ExitCode.SUCCESS
    assert "they won't be overridden" in console.display
    assert private_path.read_text(encoding="utf-8") == _IN_PLACE


async def test_skipping_still_writes_when_there_is_nothing_in_place(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)

    code = await console.execute(["--skip-if-exists"])

    assert code == ExitCode.SUCCESS
    assert "Done!" in console.display
    assert "PRIVATE KEY" in private_path.read_text(encoding="utf-8")


async def test_skipping_and_overwriting_at_once_is_refused(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = await _in_place(tmp_path)

    code = await console.execute(["--skip-if-exists", "--overwrite"])

    assert code == ExitCode.FAILURE
    assert "Both options `--skip-if-exists` and `--overwrite` cannot be combined." in (
        console.display
    )
    assert private_path.read_text(encoding="utf-8") == _IN_PLACE


async def test_overwriting_replaces_the_keys_in_place(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, public_path = await _in_place(tmp_path)

    code = await console.execute(["--overwrite"], interactive=False)

    assert code == ExitCode.SUCCESS
    assert "PRIVATE KEY" in private_path.read_text(encoding="utf-8")
    assert "PUBLIC KEY" in public_path.read_text(encoding="utf-8")


async def test_declining_the_replacement_leaves_the_keys_in_place(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = await _in_place(tmp_path)

    code = await console.execute(["--overwrite"], inputs=["n"])

    assert code == ExitCode.SUCCESS
    assert "Your action was canceled." in console.display
    assert private_path.read_text(encoding="utf-8") == _IN_PLACE


async def test_a_deployment_naming_only_its_signing_key_has_the_public_half_derived(
    tmp_path: Path,
) -> None:
    private_path, public_path = _paths(tmp_path)
    environ = {PRIVATE_KEY_VARIABLE: str(private_path)}
    async with running(
        console_kernel(_SIGNING_KEY_ONLY_APP, environ=environ),
    ) as (application, _container):
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute()

        assert code == ExitCode.SUCCESS
        assert "PRIVATE KEY" in private_path.read_text(encoding="utf-8")
        assert not public_path.exists()
        assert str(private_path) in tester.display


async def test_a_signing_key_configured_as_the_key_text_itself_names_no_file() -> None:
    # The in-memory deployment mounts its key as PEM, which is a key already
    # and names nowhere to write one.
    async with running(console_kernel(IN_MEMORY_APP)) as (application, _container):
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute()

        assert code == ExitCode.FAILURE
        assert "holds the key text itself rather than the path of a file" in tester.display


async def test_a_verifying_key_configured_as_the_key_text_itself_names_no_file(
    tmp_path: Path,
) -> None:
    # A split deployment may mount the public half as PEM, which is a key
    # already: the signing key is writable, and the other half is not.
    private_path, _public_path = _paths(tmp_path)
    environ = {
        PRIVATE_KEY_VARIABLE: str(private_path),
        PUBLIC_KEY_VARIABLE: SIGNING_KEY_PEM,
    }
    async with running(
        console_kernel(_BOTH_HALVES_APP, environ=environ),
    ) as (application, _container):
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute()

        assert code == ExitCode.FAILURE
        assert "The setting resource_server.public_key holds the key text itself" in tester.display
        assert not private_path.exists()


async def test_a_deployment_with_no_signing_key_configured_is_told_which_setting() -> None:
    async with running(console_kernel(_UNCONFIGURED_APP)) as (application, _container):
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute()

        assert code == ExitCode.FAILURE
        assert "The setting authorization_server.private_key is not configured" in tester.display
        assert "<app>/config/packages/oauth2_server.py" in tester.display


async def test_a_key_is_never_written_through_a_symbolic_link(
    console: CommandTester,
    tmp_path: Path,
) -> None:
    private_path, _public_path = _paths(tmp_path)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.symlink_to(tmp_path / "planted.pem")

    code = await console.execute(["--overwrite"], interactive=False)

    assert code == ExitCode.FAILURE
    assert "never written through a symbolic link" in console.display
    assert not (tmp_path / "planted.pem").exists()
