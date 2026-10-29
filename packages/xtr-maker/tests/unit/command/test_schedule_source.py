"""Unit tests for :mod:`xtr_maker.command._schedule_source`."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_maker import ClassName
from xtr_maker.command._schedule_source import ScheduleSource, needs_arguments

_PROVIDER = ClassName.create("report", root_package="app", kind="scheduler", suffix="Schedule")


@dataclass(frozen=True, slots=True)
class _Defaulted:
    reason: str = "nightly"
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Required:
    reason: str


class _Variadic:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


class Outer:
    class Ping:
        pass


def _source(message: type | None, *, final_classes: bool = True) -> ScheduleSource:
    return ScheduleSource(
        provider=_PROVIDER,
        schedule="default",
        message=message,
        stateful=False,
        lock=False,
        final_classes=final_classes,
    )


def test_a_message_whose_fields_all_have_defaults_needs_no_arguments() -> None:
    assert not needs_arguments(_Defaulted)


def test_a_message_with_a_required_field_needs_arguments() -> None:
    assert needs_arguments(_Required)


def test_variadic_parameters_are_not_required() -> None:
    assert not needs_arguments(_Variadic)


def test_a_nested_message_is_imported_by_its_outer_class() -> None:
    context = _source(Outer.Ping).context()

    assert f"from {__name__} import Outer" in str(context["imports"])
    assert 'RecurringMessage.every("1 hour", Outer.Ping()),' in str(context["body"])


def test_final_is_not_imported_when_classes_are_left_open() -> None:
    context = _source(None, final_classes=False).context()

    assert "final" not in str(context["imports"])
