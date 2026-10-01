from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_console import (
    Application,
    ApplicationTester,
    CommandInvokerInterface,
    ConsoleStyle,
    ExitCode,
    MissingContainerError,
)
from xtr_console.command import commands_declared_on

from xtr_password_hasher import (
    NativePasswordHasher,
    PasswordHasherFactory,
    PasswordHasherInterface,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
)
from xtr_password_hasher.command import UserPasswordHashCommand

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_console import CommandArguments, CommandDescriptor, CommandSignature

pytestmark = pytest.mark.anyio


class _User:
    def get_password(self) -> str | None:
        return None


class _Admin:
    def get_password(self) -> str | None:
        return None


class _Outer:
    class Nested:
        def get_password(self) -> str | None:
            return None


_USER = f"{_User.__module__}:{_User.__qualname__}"
_ADMIN = f"{_Admin.__module__}:{_Admin.__qualname__}"


def _argon2() -> NativePasswordHasher:
    return NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)


def _command(hasher: PasswordHasherInterface) -> UserPasswordHashCommand:
    return UserPasswordHashCommand(PasswordHasherFactory({_User: hasher}), (_USER,))


@final
class _BuildingInvoker(CommandInvokerInterface):
    """Builds the command with its factory, as a container would."""

    def __init__(self, command: UserPasswordHashCommand) -> None:
        self._command = command

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        # The arguments come parsed off the command line, typed only as objects.
        call = cast("Callable[..., Awaitable[object]]", self._command)
        return await call(*arguments.args, **arguments.kwargs)


def _tester(command: UserPasswordHashCommand) -> ApplicationTester:
    application = Application("test", catch_exceptions=False)
    application.use_invoker(_BuildingInvoker(command))
    return ApplicationTester(application, width=400)


def _style(*answers: str, interactive: bool = False) -> tuple[ConsoleStyle, io.StringIO]:
    out = io.StringIO()
    style = ConsoleStyle(
        out,
        out,
        width=400,
        decorated=False,
        interactive=interactive,
        input_stream=io.StringIO("".join(f"{answer}\n" for answer in answers)),
    )
    return style, out


def _value(display: str, key: str) -> str | None:
    for line in display.splitlines():
        label, _, value = line.strip().partition(": ")
        if label == key:
            return value
    return None


def test_the_command_is_declared_under_its_name() -> None:
    names = {
        name
        for descriptor in commands_declared_on(UserPasswordHashCommand)
        for name in descriptor.names
    }

    assert "security:hash-password" in names


async def test_it_cannot_run_without_a_factory() -> None:
    tester = ApplicationTester(Application("test", catch_exceptions=False))

    with pytest.raises(MissingContainerError, match="factory"):
        _ = await tester.execute(["security:hash-password", "secret"])


async def test_it_hashes_with_a_self_salting_hasher() -> None:
    tester = _tester(_command(_argon2()))

    code = await tester.execute(["security:hash-password", "secret"], interactive=False)

    hashed = _value(tester.display, "Password hash")
    assert code == ExitCode.SUCCESS
    assert hashed is not None
    assert _argon2().verify(hashed, "secret")
    assert _value(tester.display, "Hasher used") == "NativePasswordHasher"
    assert _value(tester.display, "Generated salt") is None
    assert "Self-salting hasher used" in tester.display
    assert "Password hashing succeeded" in tester.display


async def test_it_asks_for_the_password_when_omitted() -> None:
    tester = _tester(_command(_argon2()))

    code = await tester.execute(["security:hash-password"], inputs=["secret"])

    hashed = _value(tester.display, "Password hash")
    assert code == ExitCode.SUCCESS
    assert "Password Hash Utility" in tester.display
    assert hashed is not None
    assert _argon2().verify(hashed, "secret")


async def test_it_asks_again_after_a_blank_password() -> None:
    tester = _tester(_command(_argon2()))

    code = await tester.execute(["security:hash-password"], inputs=["  ", "secret"])

    assert code == ExitCode.SUCCESS
    assert "The password must not be empty." in tester.display


async def test_it_gives_up_after_twenty_blank_passwords() -> None:
    style, out = _style(*[""] * 20, interactive=True)

    code = await _command(_argon2())(style)

    assert code == ExitCode.FAILURE
    assert out.getvalue().count("The password must not be empty.") == 21


async def test_a_missing_password_fails_without_interaction() -> None:
    tester = _tester(_command(_argon2()))

    code = await tester.execute(["security:hash-password"], interactive=False)

    assert code == ExitCode.FAILURE
    assert "The password must not be empty." in tester.display


async def test_a_password_argument_is_warned_about_when_interactive() -> None:
    tester = _tester(_command(_argon2()))

    _ = await tester.execute(["security:hash-password", "secret"])

    assert "exposes it to shell history" in tester.display


async def test_a_password_argument_is_not_warned_about_without_interaction() -> None:
    tester = _tester(_command(_argon2()))

    _ = await tester.execute(["security:hash-password", "secret"], interactive=False)

    assert "exposes it to shell history" not in tester.display


async def test_a_dash_reads_the_password_from_standard_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("secret\r\n"))
    style, out = _style()

    code = await _command(PlaintextPasswordHasher())(style, "-", empty_salt=True)

    assert code == ExitCode.SUCCESS
    assert _value(out.getvalue(), "Password hash") == "secret"


async def test_an_empty_standard_input_fails_without_interaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    style, out = _style()

    code = await _command(_argon2())(style, "-")

    assert code == ExitCode.FAILURE
    assert "The password must not be empty." in out.getvalue()


async def test_a_legacy_hasher_gets_a_generated_salt() -> None:
    style, out = _style()

    code = await _command(Pbkdf2PasswordHasher())(style, "secret")

    salt = _value(out.getvalue(), "Generated salt")
    assert code == ExitCode.SUCCESS
    assert salt is not None
    assert len(salt) == 40
    assert _value(out.getvalue(), "Password hash") == Pbkdf2PasswordHasher().hash("secret", salt)
    assert "fits the salt length: 40 chars" in out.getvalue()


async def test_two_generated_salts_differ() -> None:
    command = _command(PlaintextPasswordHasher())
    first, first_out = _style()
    second, second_out = _style()

    _ = await command(first, "secret")
    _ = await command(second, "secret")

    first_salt = _value(first_out.getvalue(), "Generated salt")
    assert first_salt != _value(second_out.getvalue(), "Generated salt")


async def test_empty_salt_hashes_a_legacy_hasher_without_one() -> None:
    tester = _tester(_command(Pbkdf2PasswordHasher()))

    code = await tester.execute(
        ["security:hash-password", "secret", "--empty-salt"], interactive=False
    )

    assert code == ExitCode.SUCCESS
    assert _value(tester.display, "Password hash") == Pbkdf2PasswordHasher().hash("secret")
    assert _value(tester.display, "Generated salt") is None
    assert "Self-salting" not in tester.display


async def test_an_interactive_run_generates_a_salt_once_confirmed() -> None:
    style, out = _style("y", interactive=True)

    code = await _command(PlaintextPasswordHasher())(style, "secret")

    salt = _value(out.getvalue(), "Generated salt")
    assert code == ExitCode.SUCCESS
    assert "let them generate their own salt" in out.getvalue()
    assert _value(out.getvalue(), "Password hash") == f"secret{{{salt}}}"


async def test_an_interactive_run_declining_the_salt_hashes_without_one() -> None:
    style, out = _style("n", interactive=True)

    code = await _command(PlaintextPasswordHasher())(style, "secret")

    assert code == ExitCode.SUCCESS
    assert _value(out.getvalue(), "Password hash") == "secret"
    assert _value(out.getvalue(), "Generated salt") is None


async def test_a_self_salting_hasher_is_never_offered_a_salt() -> None:
    style, out = _style(interactive=True)

    code = await _command(_argon2())(style, "secret")

    assert code == ExitCode.SUCCESS
    assert "Confirm salt generation" not in out.getvalue()


async def test_it_uses_the_first_user_class_by_default() -> None:
    factory = PasswordHasherFactory(
        {_User: PlaintextPasswordHasher(), _Admin: Pbkdf2PasswordHasher()}
    )
    style, out = _style()

    code = await UserPasswordHashCommand(factory, (_USER, _ADMIN))(style, "secret")

    assert code == ExitCode.SUCCESS
    assert _value(out.getvalue(), "Hasher used") == "PlaintextPasswordHasher"


async def test_it_asks_which_user_class_when_there_are_several() -> None:
    factory = PasswordHasherFactory(
        {_User: PlaintextPasswordHasher(), _Admin: Pbkdf2PasswordHasher()}
    )
    style, out = _style(_ADMIN, interactive=True)

    code = await UserPasswordHashCommand(factory, (_USER, _ADMIN))(style, "secret", empty_salt=True)

    assert code == ExitCode.SUCCESS
    assert "For which user class" in out.getvalue()
    assert _value(out.getvalue(), "Hasher used") == "Pbkdf2PasswordHasher"


async def test_it_reports_when_no_user_class_is_configured() -> None:
    style, out = _style()

    code = await UserPasswordHashCommand(PasswordHasherFactory({}))(style, "secret")

    assert code == ExitCode.INVALID
    assert "There are no configured password hashers." in out.getvalue()


async def test_a_hasher_name_is_looked_up_as_it_is() -> None:
    command = UserPasswordHashCommand(PasswordHasherFactory({"admin": PlaintextPasswordHasher()}))
    style, out = _style()

    code = await command(style, "secret", "admin", empty_salt=True)

    assert code == ExitCode.SUCCESS
    assert _value(out.getvalue(), "Password hash") == "secret"


@pytest.mark.parametrize(
    "user_class", ["no.such.module:Thing", ":Thing", "xtr_password_hasher:Nope"]
)
async def test_an_unimportable_user_class_is_invalid(user_class: str) -> None:
    style, out = _style()

    code = await UserPasswordHashCommand(PasswordHasherFactory({}))(style, "secret", user_class)

    assert code == ExitCode.INVALID
    assert "Could not import" in out.getvalue()


async def test_a_user_class_that_is_not_a_class_is_invalid() -> None:
    style, out = _style()

    code = await UserPasswordHashCommand(PasswordHasherFactory({}))(
        style, "secret", "xtr_password_hasher:MAX_PASSWORD_LENGTH"
    )

    assert code == ExitCode.INVALID
    assert "is not a class" in out.getvalue()


async def test_an_unconfigured_user_class_is_invalid() -> None:
    style, out = _style()

    code = await UserPasswordHashCommand(PasswordHasherFactory({}))(style, "secret", _USER)

    assert code == ExitCode.INVALID
    assert "No password hasher" in out.getvalue()


async def test_an_over_long_password_fails() -> None:
    style, out = _style()

    code = await _command(_argon2())(style, "a" * 4097)

    assert code == ExitCode.FAILURE
    assert "more than the 4096" in out.getvalue()


async def test_a_nested_user_class_is_imported_by_its_qualified_name() -> None:
    nested = _Outer.Nested
    factory = PasswordHasherFactory({nested: PlaintextPasswordHasher()})
    style, out = _style()

    code = await UserPasswordHashCommand(factory, (f"{nested.__module__}:{nested.__qualname__}",))(
        style, "secret", empty_salt=True
    )

    assert code == ExitCode.SUCCESS
    assert _value(out.getvalue(), "Hasher used") == "PlaintextPasswordHasher"
