"""``security:hash-password``: hash a password from the command line."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Annotated, Final, cast, final

from typing_extensions import override
from xtr_console import Argument, ConsoleStyle, ExitCode, as_command, escape

from xtr_password_hasher.exception import PasswordHasherError
from xtr_password_hasher.hasher.create_auto_password_hasher import create_auto_password_hasher
from xtr_password_hasher.hasher.password_hasher_factory_interface import (
    PasswordHasherFactoryInterface,
)

if TYPE_CHECKING:
    from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

__all__ = ["UserPasswordHashCommand"]


@final
class _NoFactory(PasswordHasherFactoryInterface):
    """The default of the command's ``factory`` parameter: no container wired one.

    Typed as what a container fills the parameter with, so the engine still
    matches and injects the real factory; ``PasswordHasherFactoryInterface |
    None`` is a different type the engine never fills.
    """

    __slots__ = ()

    @override
    def get_password_hasher(self, user: str | type | object) -> PasswordHasherInterface:
        del user
        message = "no password hasher factory was wired"
        raise RuntimeError(message)


_UNSET_FACTORY: Final[PasswordHasherFactoryInterface] = _NoFactory()


@as_command("security:hash-password")
@final
class UserPasswordHashCommand:
    """Hashes a password and prints the hash and the hasher that made it.

    With no ``user-class`` the secure default hasher (argon2id, verifying
    bcrypt and PBKDF2 behind it) is used. Naming a user class as
    ``module:Class`` asks the configured factory for that class's hasher — only
    available when a container wired the factory in.
    """

    __slots__ = ("_factory",)

    def __init__(self, factory: PasswordHasherFactoryInterface = _UNSET_FACTORY) -> None:
        """Resolve a user class's hasher through ``factory`` when one is wired."""
        self._factory = None if factory is _UNSET_FACTORY else factory

    async def __call__(
        self,
        io: ConsoleStyle,
        password: str | None = None,
        user_class: Annotated[str | None, Argument(name="user-class")] = None,
    ) -> int:
        """Hash ``password`` and print the result.

        Args:
            io: Where the command writes.
            password: The plaintext to hash; asked for, hidden, when omitted.
            user_class: A ``module:Class`` whose configured hasher to use.
        """
        hasher = self._resolve_hasher(io, user_class)
        if hasher is None:
            return ExitCode.INVALID

        plain = password if password is not None else io.ask_hidden("Password")

        try:
            hashed = hasher.hash(plain)
        except PasswordHasherError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE

        io.title("Password hasher")
        io.text(f"Hasher: {escape(type(hasher).__name__)}")
        io.text(f"Algorithm: {escape(_algorithm_of(hashed))}")
        io.text("Hash:")
        io.text(escape(hashed))
        io.success("Password hashing succeeded.")
        return ExitCode.SUCCESS

    def _resolve_hasher(
        self,
        io: ConsoleStyle,
        user_class: str | None,
    ) -> PasswordHasherInterface | None:
        if user_class is None:
            return create_auto_password_hasher()
        if self._factory is None:
            io.error(
                "Naming a user class needs a configured factory, which only a "
                "container provides. Run without a user class to use the default hasher.",
            )
            return None
        cls = _import_class(io, user_class)
        if cls is None:
            return None
        try:
            return self._factory.get_password_hasher(cls)
        except PasswordHasherError as error:
            io.error(escape(str(error)))
            return None


def _import_class(io: ConsoleStyle, user_class: str) -> type | None:
    if ":" not in user_class:
        io.error(f'A user class is written "module:Class", not "{escape(user_class)}".')
        return None
    module_name, _, class_name = user_class.partition(":")
    try:
        module = importlib.import_module(module_name)
        found = cast("object", getattr(module, class_name))
    except (ImportError, AttributeError):
        io.error(f'Could not import "{escape(user_class)}".')
        return None
    if not isinstance(found, type):
        io.error(f'"{escape(user_class)}" is not a class.')
        return None
    return found


def _algorithm_of(hashed: str) -> str:
    if hashed.startswith("$argon2id$"):
        return "argon2id"
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        return "bcrypt"
    if hashed.startswith("$pbkdf2-"):
        return "pbkdf2"
    return "plaintext"
