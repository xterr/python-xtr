from __future__ import annotations

import io

import pytest
from xtr_console import Application, ApplicationTester, ConsoleStyle, ExitCode
from xtr_console.command import commands_declared_on

from xtr_password_hasher import (
    NativePasswordHasher,
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
)
from xtr_password_hasher.command import UserPasswordHashCommand
from xtr_password_hasher.command.user_password_hash_command import _NoFactory

pytestmark = pytest.mark.anyio


class _User:
    def get_password(self) -> str | None:
        return None


def _style() -> tuple[ConsoleStyle, io.StringIO]:
    out = io.StringIO()
    return ConsoleStyle(out, out, width=200, decorated=False, interactive=False), out


@pytest.fixture
def tester() -> ApplicationTester:
    return ApplicationTester(Application("test", catch_exceptions=False))


def _hash_from(display: str) -> str:
    lines = [line.strip() for line in display.splitlines() if line.strip()]
    marker = lines.index("Hash:")
    return lines[marker + 1]


async def test_it_hashes_a_password_given_as_an_argument(tester: ApplicationTester) -> None:
    code = await tester.execute(["security:hash-password", "secret"])

    assert code == ExitCode.SUCCESS
    assert "Algorithm: argon2id" in tester.display
    assert NativePasswordHasher("argon2id").verify(_hash_from(tester.display), "secret")


async def test_it_asks_for_the_password_when_omitted(tester: ApplicationTester) -> None:
    code = await tester.execute(["security:hash-password"], inputs=["secret"])

    assert code == ExitCode.SUCCESS
    assert NativePasswordHasher("argon2id").verify(_hash_from(tester.display), "secret")


async def test_it_reports_the_hasher_class(tester: ApplicationTester) -> None:
    _ = await tester.execute(["security:hash-password", "secret"])

    assert "Hasher: MigratingPasswordHasher" in tester.display


async def test_a_user_class_without_a_container_is_invalid(tester: ApplicationTester) -> None:
    code = await tester.execute(["security:hash-password", "secret", "acme:User"])

    assert code == ExitCode.INVALID
    assert "needs a configured factory" in tester.display


def test_the_command_is_declared_under_its_name() -> None:
    names = {
        name
        for descriptor in commands_declared_on(UserPasswordHashCommand)
        for name in descriptor.names
    }

    assert "security:hash-password" in names


@pytest.mark.parametrize(
    ("hasher", "algorithm"),
    [
        (NativePasswordHasher("bcrypt", cost=4), "bcrypt"),
        (Pbkdf2PasswordHasher(iterations=1000), "pbkdf2"),
        (PlaintextPasswordHasher(), "plaintext"),
    ],
)
async def test_it_reports_the_algorithm_of_each_hasher(
    hasher: NativePasswordHasher | Pbkdf2PasswordHasher | PlaintextPasswordHasher,
    algorithm: str,
) -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({_User: hasher}))
    style, out = _style()

    code = await command(style, "secret", f"{_User.__module__}:{_User.__qualname__}")

    assert code == ExitCode.SUCCESS
    assert f"Algorithm: {algorithm}" in out.getvalue()


async def test_a_user_class_without_a_colon_is_invalid() -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({}))
    style, out = _style()

    code = await command(style, "secret", "NotAModuleClass")

    assert code == ExitCode.INVALID
    assert 'written "module:Class"' in out.getvalue()


async def test_an_unimportable_user_class_is_invalid() -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({}))
    style, out = _style()

    code = await command(style, "secret", "no.such.module:Thing")

    assert code == ExitCode.INVALID
    assert "Could not import" in out.getvalue()


async def test_a_user_class_that_is_not_a_class_is_invalid() -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({}))
    style, out = _style()

    code = await command(style, "secret", "xtr_password_hasher:MAX_PASSWORD_LENGTH")

    assert code == ExitCode.INVALID
    assert "is not a class" in out.getvalue()


async def test_an_unconfigured_user_class_is_invalid() -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({}))
    style, out = _style()

    code = await command(style, "secret", f"{_User.__module__}:{_User.__qualname__}")

    assert code == ExitCode.INVALID
    assert "No password hasher" in out.getvalue()


async def test_an_over_long_password_fails() -> None:
    command = UserPasswordHashCommand()
    style, out = _style()

    code = await command(style, "a" * 4097)

    assert code == ExitCode.FAILURE
    assert "more than the 4096" in out.getvalue()


def test_the_unset_factory_sentinel_implements_the_factory_interface() -> None:
    assert PasswordHasherFactoryInterface in _NoFactory.__mro__


def test_the_unset_factory_sentinel_is_never_meant_to_resolve() -> None:
    with pytest.raises(RuntimeError):
        _ = _NoFactory().get_password_hasher(_User())
