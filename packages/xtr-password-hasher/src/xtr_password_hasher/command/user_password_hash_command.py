"""``security:hash-password``: hash a password from the command line."""

from __future__ import annotations

import base64
import importlib
import secrets
import sys
from typing import TYPE_CHECKING, Annotated, Final, cast, final

from xtr_console import Argument, ConsoleStyle, ExitCode, as_command, escape

from xtr_password_hasher.exception import PasswordHasherError
from xtr_password_hasher.hasher.migrating_password_hasher import hash_with_salt

# A container reads the constructor's annotations at runtime to fill it.
from xtr_password_hasher.hasher.password_hasher_factory_interface import (
    PasswordHasherFactoryInterface,  # noqa: TC001
)
from xtr_password_hasher.legacy_password_hasher_interface import is_legacy_password_hasher

if TYPE_CHECKING:
    from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

__all__ = ["UserPasswordHashCommand"]

_SALT_BYTES: Final = 30
_PASSWORD_ATTEMPTS: Final = 20
_BLANK_MESSAGE: Final = "The password must not be empty."
_FROM_STDIN: Final = "-"


@as_command("security:hash-password")
@final
class UserPasswordHashCommand:
    """Hashes a password the way the application's configuration would.

    The hasher is the one configured for ``user-class`` — a ``module:Class``,
    or the name of a configured hasher — or, when it is left out, for the
    first of ``user_classes`` (asked, when there are several and the run is
    interactive). ``user_classes`` are the keys the factory is configured
    with, as ``module:Class`` strings or hasher names.

    The password is asked for, hidden, when left out; ``-`` reads it from
    standard input, which keeps it out of the shell history and the process
    list. A hasher that takes its salt from outside gets a generated one,
    printed with the hash, unless ``--empty-salt`` is given.
    """

    __slots__ = ("_factory", "_user_classes")

    def __init__(
        self,
        factory: PasswordHasherFactoryInterface,
        user_classes: tuple[str, ...] = (),
    ) -> None:
        """Resolve hashers through ``factory``, defaulting to the first of ``user_classes``."""
        self._factory = factory
        self._user_classes = user_classes

    async def __call__(
        self,
        io: ConsoleStyle,
        password: str | None = None,
        user_class: Annotated[str | None, Argument(name="user-class")] = None,
        *,
        empty_salt: bool = False,
    ) -> int:
        """Hash a user password.

        Args:
            io: Where the command writes.
            password: The plain password to hash; ``-`` reads it from standard
                input.
            user_class: The ``module:Class`` of the user, or the name of the
                hasher, whose configured hasher to use.
            empty_salt: Do not generate a salt; let the hasher do without one.
        """
        if io.interactive:
            io.title("Password Hash Utility")
        else:
            io.newline()

        password = _given_password(io, password)
        hasher = self._resolve_hasher(io, user_class)
        if hasher is None:
            return ExitCode.INVALID

        self_salting = not empty_salt and not is_legacy_password_hasher(hasher)
        generate_salt = not empty_salt and not self_salting

        if not password:
            password = _ask_password(io) if io.interactive else None
            if password is None:
                io.error(_BLANK_MESSAGE)
                return ExitCode.FAILURE

        salt = _salt(io) if generate_salt else None

        try:
            hashed_password = hash_with_salt(hasher, password, salt)
        except PasswordHasherError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE

        # Written unwrapped: a table cell or a wrapped line would cut the hash,
        # which is printed to be copied whole.
        io.console.print(f"Hasher used: {type(hasher).__name__}", markup=False, soft_wrap=True)
        io.console.print(f"Password hash: {hashed_password}", markup=False, soft_wrap=True)
        if salt is not None:
            io.console.print(f"Generated salt: {salt}", markup=False, soft_wrap=True)

        if salt is not None:
            io.note(
                f"Make sure that your salt storage field fits the salt length: {len(salt)} chars"
            )
        elif self_salting:
            io.note("Self-salting hasher used: the hasher generated its own built-in salt.")

        io.success("Password hashing succeeded")
        return ExitCode.SUCCESS

    def _resolve_hasher(
        self,
        io: ConsoleStyle,
        user_class: str | None,
    ) -> PasswordHasherInterface | None:
        if user_class is None:
            if not self._user_classes:
                io.error("There are no configured password hashers.")
                return None
            user_class = self._choose_user_class(io)
        target = _import_class(io, user_class) if ":" in user_class else user_class
        if target is None:
            return None
        try:
            return self._factory.get_password_hasher(target)
        except PasswordHasherError as error:
            io.error(escape(str(error)))
            return None

    def _choose_user_class(self, io: ConsoleStyle) -> str:
        if not io.interactive or len(self._user_classes) == 1:
            return self._user_classes[0]
        choices = sorted(self._user_classes, key=str.casefold)
        return io.ask(
            "For which user class would you like to hash a password?",
            choices[0],
            choices=choices,
        )


def _given_password(io: ConsoleStyle, password: str | None) -> str | None:
    """Read ``-`` from standard input; warn about a password typed on the command line."""
    if password == _FROM_STDIN:
        return sys.stdin.readline().rstrip("\r\n")
    if password and io.interactive:
        io.warning(
            "Passing the password as a command argument exposes it to shell history and "
            'the process list; prefer the interactive prompt or pass "-" to read it from '
            "standard input.",
        )
    return password


def _ask_password(io: ConsoleStyle) -> str | None:
    """Ask, hidden, until a non-blank password is typed or the attempts run out."""
    for _ in range(_PASSWORD_ATTEMPTS):
        answer = io.ask_hidden("Type in your password to be hashed")
        if answer.strip():
            return answer
        io.error(_BLANK_MESSAGE)
    return None


def _salt(io: ConsoleStyle) -> str | None:
    """Generate a salt — once confirmed, when someone is there to confirm it."""
    if io.interactive:
        io.note(
            "The command will take care of generating a salt for you. Be aware that some "
            "hashers advise to let them generate their own salt. If you're using one of "
            "those hashers, please answer 'no' to the question below. Provide the "
            "'--empty-salt' option in order to let the hasher handle the generation itself.",
        )
        if not io.confirm("Confirm salt generation?", default=True):
            return None
    return base64.b64encode(secrets.token_bytes(_SALT_BYTES)).decode("ascii")


def _import_class(io: ConsoleStyle, user_class: str) -> type | None:
    module_name, _, class_name = user_class.partition(":")
    try:
        module = importlib.import_module(module_name)
        found = cast("object", module)
        for name in class_name.split("."):
            found = cast("object", getattr(found, name))
    except (ImportError, AttributeError, ValueError):
        io.error(f'Could not import "{escape(user_class)}".')
        return None
    if not isinstance(found, type):
        io.error(f'"{escape(user_class)}" is not a class.')
        return None
    return found
