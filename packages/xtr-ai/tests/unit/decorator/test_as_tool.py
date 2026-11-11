from __future__ import annotations

import pytest
from typing_extensions import override

from xtr_ai.decorator import TOOL_ATTRIBUTE, ToolDeclaration, as_tool, tools_declared_on
from xtr_ai.exception import InvalidConfigurationError


class Weather:
    @as_tool(agents=("chat", "ops"), name="forecast", description="Tomorrow.")
    def tomorrow(self, city: str) -> str:
        return f"sunny in {city}"

    def helper(self) -> None: ...


class Overridden(Weather):
    @override
    def tomorrow(self, city: str) -> str:  # no decorator: not a tool any more
        return city


class Extended(Weather):
    @as_tool(agents=("chat",))
    def today(self) -> str:
        return "rain"


def test_a_method_records_its_declaration() -> None:
    declaration = getattr(Weather.tomorrow, TOOL_ATTRIBUTE)

    assert declaration == ToolDeclaration("tomorrow", ("chat", "ops"), "forecast", "Tomorrow.")


def test_at_least_one_agent_is_named() -> None:
    with pytest.raises(InvalidConfigurationError, match="at least one agent"):
        _ = as_tool(agents=())


def test_a_module_level_function_is_refused() -> None:
    def tool() -> None: ...

    with pytest.raises(InvalidConfigurationError, match="is a function"):
        _ = as_tool(agents=("chat",))(tool)


def test_declarations_are_read_off_a_class() -> None:
    assert [d.method for d in tools_declared_on(Weather)] == ["tomorrow"]


def test_inherited_declarations_are_read_and_overrides_drop_them() -> None:
    assert sorted(d.method for d in tools_declared_on(Extended)) == ["today", "tomorrow"]
    assert list(tools_declared_on(Overridden)) == []


def test_anything_but_a_class_declares_nothing() -> None:
    assert list(tools_declared_on(Weather())) == []
    assert list(tools_declared_on(len)) == []
