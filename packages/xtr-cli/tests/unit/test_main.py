from __future__ import annotations

from typing import final

import pytest
from xtr_console import ApplicationTester, ExitCode

import xtr_cli.__main__ as main_module
from tests.support import build_tester
from xtr_cli import __version__
from xtr_cli.__main__ import main


@final
class _FakeApplication:
    def __init__(self, name: str, version: str | None, description: str | None) -> None:
        self.name = name
        self.version = version
        self.description = description

    def run(self) -> int:
        return 7


def test_the_application_is_named_xtr_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[_FakeApplication] = []

    def factory(name: str, version: str | None, description: str | None) -> _FakeApplication:
        built.append(_FakeApplication(name, version, description))
        return built[-1]

    monkeypatch.setattr(main_module, "Application", factory)

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 7
    assert [(one.name, one.version, bool(one.description)) for one in built] == [
        ("xtr", __version__, True)
    ]


@pytest.mark.anyio
async def test_the_help_lists_both_commands_and_their_aliases() -> None:
    tester: ApplicationTester = build_tester()

    code = await tester.execute(["--help"])

    assert code == ExitCode.SUCCESS
    for name in ("project:new (new)", "project:init (init)"):
        assert name in tester.display
