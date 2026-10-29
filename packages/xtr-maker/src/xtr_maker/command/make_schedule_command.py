"""``make:schedule``: the provider of a schedule, sending one of the application's messages."""

from __future__ import annotations

import re
from typing import Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import (  # noqa: TC002 — the container reads annotations at runtime.
    Injected,
    KernelInterface,
)
from xtr_messenger import declared_names, type_for_name
from xtr_scheduler import Schedule
from xtr_scheduler.schedule_provider_locator import (  # noqa: TC002 — the container reads annotations at runtime.
    ScheduleProviderLocator,
)

from xtr_maker.class_name import ClassName
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.

from ._schedule_source import ScheduleSource, needs_arguments

__all__ = ["MakeScheduleCommand"]

_EMPTY: Final = "[empty schedule]"
"""The message choice that writes a schedule sending nothing yet."""

_ATTEMPTS: Final = 3
"""How many times a name is asked: an input that has ended answers empty every time."""

_SCHEDULE_NAME: Final = re.compile(r"[A-Za-z0-9_.-]+")
"""What a schedule name may hold: it is part of the transport's DSN and the receiver's name."""

_PEERS: Final = {
    "stateful": ("cache", "xtr_cache.bundle:CacheBundle"),
    "lock": ("lock", "xtr_lock.bundle:LockBundle"),
}
"""Each option's bundle, by name and by the class an application activates."""

_QUESTIONS: Final = {
    "stateful": "Keep what already ran in the scheduler cache pool?",
    "lock": "Send from the worker holding a lock only?",
}

_TEMPLATE: Final = "scheduler/schedule.py.jinja"


@final
@as_command("make:schedule", description="Write the provider of a schedule.")
class MakeScheduleCommand:
    """Writes ``scheduler/<name>_schedule.py``: an ``@as_schedule`` provider.

    The schedule sends one of the application's ``@as_message`` classes every
    hour, or nothing yet; a message whose constructor takes arguments is left
    out with a comment saying how to add it, so the file imports and the
    kernel boots before they are known. It can keep its state in the
    ``scheduler`` cache pool (``--stateful``, with the cache bundle active)
    and run under a lock (``--lock``, with the lock bundle active).

    Whatever is not on the command line is asked. Without a terminal (``-n``)
    the schedule is ``default``, it sends nothing and has neither state nor
    lock, but the name must be given.
    """

    __slots__ = ("_bundles", "_file_manager", "_schedules")

    def __init__(
        self, file_manager: FileManager, schedules: ScheduleProviderLocator, kernel: KernelInterface
    ) -> None:
        """Write into the package ``file_manager`` holds, beside the schedules declared.

        Args:
            file_manager: The application package the provider is written into.
            schedules: The schedules the application declares; one a declared
                provider already provides is refused.
            kernel: The kernel; its active bundles decide which options apply.
        """
        self._file_manager = file_manager
        self._schedules = schedules
        self._bundles = frozenset(kernel.bundles)

    async def __call__(  # noqa: PLR0913 — the command's own options, each a parameter.
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        *,
        schedule: str | None = None,
        message: str | None = None,
        stateful: bool = False,
        lock: bool = False,
    ) -> int:
        """Write the provider of a schedule.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the file.
            name: The provider's class name, such as ``ReportSchedule`` or
                ``"report"``; ``reporting.Report`` writes it under
                ``scheduler/reporting/``.
            schedule: The schedule it provides; defaults to ``default``.
            message: The message it sends every hour, by class name or as
                ``module:Class``; left out, it sends nothing yet.
            stateful: Keep what already ran in the ``scheduler`` cache pool.
            lock: Send from the worker holding a lock only.
        """
        try:
            source = ScheduleSource(
                provider=self._provider_name(io, name),
                schedule=self._schedule_name(io, schedule),
                message=self._message(io, message),
                stateful=self._option(io, "stateful", given=stateful),
                lock=self._option(io, "lock", given=lock),
                final_classes=generator.final_classes,
            )
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        try:
            path = generator.generate_class(source.provider, _TEMPLATE, source.context())
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(
            f"Wrote {source.provider.short_name}, which provides the {source.schedule} schedule."
        )
        relative = escape(self._file_manager.relative(path))
        io.text("Next:")
        if source.message is not None and needs_arguments(source.message):
            short = source.message.__qualname__
            io.text(f"  - Open {relative} and add {short} once its arguments are known.")
        else:
            io.text(f"  - Open {relative} and set what it sends, and how often.")
        io.text(f"  - Run it: messenger:consume scheduler_{escape(source.schedule)}")
        return ExitCode.SUCCESS

    def _provider_name(self, io: ConsoleStyle, typed: str | None) -> ClassName:
        """Return the provider class ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be asked.
            InvalidClassNameError: When the name cannot name a class, or no
                answer could after the last attempt.
        """
        if typed is not None:
            return self._provider_class(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the provider to write: make:schedule <name>,"
                " such as make:schedule ReportSchedule."
            )
        question = "The provider's class name (such as [cyan]ReportSchedule[/])"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._provider_class(io.ask(question))
            except InvalidClassNameError as error:
                io.error(escape(str(error)))
        return self._provider_class(io.ask(question))

    def _provider_class(self, typed: str) -> ClassName:
        return ClassName.create(
            typed, root_package=self._file_manager.root_package, kind="scheduler", suffix="Schedule"
        )

    def _schedule_name(self, io: ConsoleStyle, typed: str | None) -> str:
        """Return the schedule ``typed`` names, or the one asked for, ``default`` by default.

        Raises:
            InvalidArgumentError: When the name holds a character a schedule
                name cannot, or a declared provider already provides it.
        """
        if typed is not None or not io.interactive:
            return self._free_schedule("default" if typed is None else typed)
        question = "The schedule it provides"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._free_schedule(io.ask(question, "default"))
            except InvalidArgumentError as error:
                io.error(escape(str(error)))
        return self._free_schedule(io.ask(question, "default"))

    def _free_schedule(self, typed: str) -> str:
        """Return ``typed`` when no provider declared in the application provides it.

        A schedule only tasks are declared on has no provider yet, so it may
        get this one; the tasks join it.

        Raises:
            InvalidArgumentError: When the name is not one, or is taken.
        """
        name = typed.strip()
        if _SCHEDULE_NAME.fullmatch(name) is None:
            raise InvalidArgumentError(
                f"{typed!r} cannot name a schedule: use letters, digits, '_', '-' or '.'."
            )
        provider = self._schedules.provided_services().get(name)
        if provider is not None and not issubclass(provider, Schedule):
            raise InvalidArgumentError(
                f"The schedule {name!r} is already provided by"
                f" {_qualified(provider)}; pick another name."
            )
        return name

    def _message(self, io: ConsoleStyle, typed: str | None) -> type | None:
        """Return the message ``typed`` names, or the one picked; ``None`` for none.

        Raises:
            InvalidArgumentError: When ``typed`` names no message declared in
                the application.
        """
        root = self._file_manager.root_package
        offered = _declared_messages(root)
        if typed is None:
            if not offered:
                return None
            answer = io.ask("The message it sends every hour", _EMPTY, choices=(_EMPTY, *offered))
            return offered.get(answer)
        accepted = {**offered, **{_qualified(found): found for found in offered.values()}}
        found = accepted.get(typed.strip())
        if found is not None:
            return found
        if not offered:
            raise InvalidArgumentError(
                f"No message is declared in {root}, so there is no {typed!r} to send;"
                " leave --message out."
            )
        raise InvalidArgumentError(
            f"There is no message {typed!r} in {root}; the declared ones are {', '.join(offered)}."
        )

    def _option(self, io: ConsoleStyle, option: str, *, given: bool) -> bool:
        """Return whether ``option`` applies: given, or confirmed when its bundle is active.

        Raises:
            InvalidArgumentError: When ``option`` was given and its bundle is
                not active.
        """
        bundle, bundle_class = _PEERS[option]
        active = bundle in self._bundles
        if given and not active:
            raise InvalidArgumentError(
                f"--{option} needs the {bundle} bundle: activate {bundle_class},"
                f" or leave --{option} out."
            )
        if given or not active:
            return given
        return io.confirm(_QUESTIONS[option])


def _declared_messages(root_package: str) -> dict[str, type]:
    """Return every ``@as_message`` class of the application, by the name it is offered under.

    The kernel imported the whole package as it scanned it, so every message
    is declared by now. A class name two of them share is offered as
    ``module:Class`` instead.
    """
    prefix = f"{root_package}."
    found = sorted(
        (
            message
            for message in map(type_for_name, declared_names())
            if message.__module__ == root_package or message.__module__.startswith(prefix)
        ),
        key=_qualified,
    )
    names = [message.__qualname__ for message in found]
    return {
        message.__qualname__ if names.count(message.__qualname__) == 1 else _qualified(message): (
            message
        )
        for message in found
    }


def _qualified(kind: type) -> str:
    return f"{kind.__module__}:{kind.__qualname__}"
