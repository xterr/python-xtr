from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_console import ExitCode

import xtr_recipes.__main__ as main_module
from tests.support import build_tester
from xtr_recipes import __version__
from xtr_recipes.__main__ import main

if TYPE_CHECKING:
    from xtr_console import ApplicationTester

_COMMANDS = (
    "recipes:add",
    "recipes:install",
    "recipes:remove",
    "recipes:show",
    "recipes:sync",
)


@final
class _FakeApplication:
    def __init__(self, name: str, version: str | None, description: str | None) -> None:
        self.name = name
        self.version = version
        self.description = description

    def run(self) -> int:
        return 7


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


def _capturing(monkeypatch: pytest.MonkeyPatch) -> list[_FakeApplication]:
    """Build a fake in place of the real application, and collect what was built."""
    built: list[_FakeApplication] = []

    def factory(name: str, version: str | None, description: str | None) -> _FakeApplication:
        application = _FakeApplication(name, version, description)
        built.append(application)
        return application

    monkeypatch.setattr(main_module, "Application", factory)
    return built


def test_it_names_and_versions_the_application_after_the_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = _capturing(monkeypatch)

    with pytest.raises(SystemExit):
        main()

    assert [(one.name, one.version) for one in built] == [("xtr-recipes", __version__)]


def test_it_exits_with_the_applications_code(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = _capturing(monkeypatch)

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 7


def test_the_application_carries_a_description(monkeypatch: pytest.MonkeyPatch) -> None:
    built = _capturing(monkeypatch)

    with pytest.raises(SystemExit):
        main()

    assert [bool(one.description) for one in built] == [True]


@pytest.mark.anyio
async def test_the_help_lists_every_command(tester: ApplicationTester) -> None:
    code = await tester.execute(["--help"])

    assert code == ExitCode.SUCCESS
    for name in _COMMANDS:
        assert name in tester.display
