from __future__ import annotations

import sys

from xtr_cli import Scaffolder, command_support


def test_the_scaffolder_runs_real_processes() -> None:
    assert isinstance(command_support.build_scaffolder(), Scaffolder)


def test_the_default_python_is_the_one_running_the_tool() -> None:
    assert command_support.default_python() == f"3.{sys.version_info.minor}"
