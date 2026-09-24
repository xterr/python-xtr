"""The fixture is opt-in, and opting in is one line.

Each case runs a real pytest in a fresh interpreter, because what is being
checked is how the plugin is discovered — which cannot be observed from
inside the run that already discovered it.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

OPT_IN = 'pytest_plugins = ["xtr_clock.pytest_plugin"]\n'


def run_pytest(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", str(directory)],
        capture_output=True,
        text=True,
        check=False,
        cwd=directory,
    )


def test_the_fixture_freezes_time_once_a_suite_opts_in(tmp_path: Path) -> None:
    _ = (tmp_path / "conftest.py").write_text(OPT_IN)
    _ = (tmp_path / "test_frozen.py").write_text(
        "from xtr_clock import MockClock, now\n"
        "\n"
        "def test_time_stands_still(clock):\n"
        "    assert isinstance(clock, MockClock)\n"
        "    first = now()\n"
        "    import time; time.sleep(0.01)\n"
        "    assert now() == first\n"
        "\n"
        "def test_the_clock_can_be_moved(clock):\n"
        "    first = now()\n"
        "    clock.sleep(3600)\n"
        "    assert (now() - first).total_seconds() == 3600\n",
    )

    result = run_pytest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_the_fixture_does_not_exist_until_a_suite_opts_in(tmp_path: Path) -> None:
    _ = (tmp_path / "test_absent.py").write_text(
        "def test_asking_for_it(clock):\n    pass\n",
    )

    result = run_pytest(tmp_path)

    assert result.returncode != 0
    assert "fixture 'clock' not found" in result.stdout


def test_the_clock_in_force_is_restored_between_tests(tmp_path: Path) -> None:
    _ = (tmp_path / "conftest.py").write_text(OPT_IN)
    _ = (tmp_path / "test_restored.py").write_text(
        "from xtr_clock import Clock, SystemClock\n"
        "\n"
        "def test_freezes(clock):\n"
        "    assert not isinstance(Clock.get(), SystemClock)\n"
        "\n"
        "def test_is_thawed_again():\n"
        "    assert isinstance(Clock.get(), SystemClock)\n",
    )

    result = run_pytest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_the_library_imports_with_no_test_framework_present() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import xtr_clock; "
                "assert 'pytest' not in sys.modules, sorted(sys.modules); "
                "print(xtr_clock.now().isoformat())"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_the_library_imports_with_nothing_but_the_standard_library() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, xtr_clock\n"
                "roots = {n.partition('.')[0] for n in sys.modules "
                "if not n.startswith('_')}\n"
                "extra = roots - set(sys.stdlib_module_names) - {'xtr_clock'}\n"
                "assert not extra, sorted(extra)\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
