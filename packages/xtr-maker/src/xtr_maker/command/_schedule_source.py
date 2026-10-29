"""What ``make:schedule``'s template reads: the provider's imports, constructor and schedule.

The schedule is written as the formatter leaves it: its message on a line of
its own with a trailing comma, and each chained call — ``.stateful(...)``,
``.lock(...)`` — on a line of its own below a comment saying what it does. The
comments keep the formatter from joining the chain onto one line, so the
layout holds however long the names are.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from xtr_maker.import_collector import ImportCollector

if TYPE_CHECKING:
    from xtr_maker.class_name import ClassName

__all__ = ["ScheduleSource", "needs_arguments"]

_EVERY: Final = '"1 hour"'
"""How often the generated schedule sends its message."""

_STATEFUL_COMMENT: Final = "Keep what ran in the scheduler cache pool, so a restart resumes."
_LOCK_COMMENT: Final = "Send from one worker only: the one holding the lock."


@final
@dataclass(frozen=True, slots=True)
class ScheduleSource:
    """The provider ``make:schedule`` writes, as the values its template reads.

    Attributes:
        provider: The provider class.
        schedule: The schedule it provides.
        message: The message it sends, ``None`` for none.
        stateful: Whether it keeps its state in the ``scheduler`` cache pool.
        lock: Whether it runs under a lock.
        final_classes: Whether the class is marked ``@final``.
    """

    provider: ClassName
    schedule: str
    message: type | None
    stateful: bool
    lock: bool
    final_classes: bool

    def context(self) -> dict[str, object]:
        """Return the template's values: imports, decorator, constructor and schedule lines."""
        imports = ImportCollector(self.provider.root_package)
        if self.final_classes:
            _ = imports.add("typing", "final")
        schedule_class = imports.add("xtr_scheduler", "Schedule")
        parameters: list[str] = []
        calls: list[tuple[str, str]] = []
        if self.stateful:
            annotated = imports.add("typing", "Annotated")
            cache = imports.add("xtr_cache_contracts", "CacheInterface")
            target = imports.add("xtr_dependency_injection", "Target")
            parameters.append(f'cache: {annotated}[{cache}, {target}("scheduler")]')
            calls.append((_STATEFUL_COMMENT, ".stateful(cache)"))
        if self.lock:
            parameters.append(f"lock_factory: {imports.add('xtr_lock', 'LockFactory')}")
            resource = _literal(f"scheduler-{self.schedule}")
            calls.append((_LOCK_COMMENT, f".lock(lock_factory.create_lock({resource}))"))
        comments, base = self._schedule_lines(imports, schedule_class)
        decorator = imports.add("xtr_scheduler.decorator", "as_schedule")
        provider_interface = imports.add("xtr_scheduler", "ScheduleProviderInterface")
        override = imports.add("typing_extensions", "override")
        return {
            "imports": imports.render(),
            "schedule": self.schedule,
            "as_schedule": f"@{decorator}({_literal(self.schedule)})",
            "provider_interface": provider_interface,
            "override": override,
            "schedule_class": schedule_class,
            "parameters": parameters,
            "init_docstring": self._init_docstring(),
            "body": [*comments, *_assignment(base, calls)],
        }

    def _schedule_lines(
        self, imports: ImportCollector, schedule_class: str
    ) -> tuple[list[str], list[str]]:
        """Return the comment above the schedule, and the schedule's own lines.

        A message whose constructor takes arguments is not built: the comment
        says how to add it, so the file imports and boots before they are known.
        """
        message = self.message
        if message is None:
            example = f"RecurringMessage.every({_EVERY}, PlaceOrder())"
            return [f"# Add what it sends, such as {example}."], [f"{schedule_class}()"]
        if needs_arguments(message):
            short = message.__qualname__
            return [
                f"# Add what it sends once {short}'s arguments are known, such as",
                f"# RecurringMessage.every({_EVERY}, {short}(...)).",
            ], [f"{schedule_class}()"]
        recurring = imports.add("xtr_scheduler", "RecurringMessage")
        top, _, nested = message.__qualname__.partition(".")
        built = ".".join(filter(None, (imports.add(message.__module__, top), nested)))
        return [], [f"{schedule_class}(", f"    {recurring}.every({_EVERY}, {built}()),", ")"]

    def _init_docstring(self) -> str:
        match self.stateful, self.lock:
            case True, True:
                return "Build the schedule, its state in ``cache``, under a ``lock_factory`` lock."
            case True, False:
                return "Build the schedule, keeping what already ran in ``cache``."
            case False, True:
                return "Build the schedule, sent under a lock from ``lock_factory``."
            case _:
                return "Build the schedule."


def needs_arguments(message: type) -> bool:
    """Report whether building ``message`` takes an argument it has no default for."""
    try:
        _ = inspect.signature(message).bind()
    except TypeError:
        return True
    return False


def _assignment(base: list[str], calls: list[tuple[str, str]]) -> list[str]:
    """Return ``self._schedule = ...``, each chained call below the comment saying what it does."""
    if not calls:
        return [f"self._schedule = {base[0]}", *base[1:]]
    lines = ["self._schedule = (", *(f"    {line}" for line in base)]
    for comment, call in calls:
        lines.extend((f"    # {comment}", f"    {call}"))
    lines.append(")")
    return lines


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)
