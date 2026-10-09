"""Every example this package shows a reader is one that runs.

The README, the agent skill and the docstrings all teach the API by example,
and an example that no longer works teaches the wrong thing — the more
convincingly for looking like documentation. Each one is executed here, so a
change to the API that leaves an example behind fails the suite rather than
the next reader.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_PACKAGE = Path(__file__).resolve().parents[1]
_SOURCE = _PACKAGE / "src" / "xtr_http_message"

_BLOCK = re.compile(r"^[ \t]*```python\n(.*?)^[ \t]*```", re.DOTALL | re.MULTILINE)


def _blocks(text: str, where: str) -> Iterator[tuple[str, str]]:
    """Yield every fenced example in ``text``, each with a name saying where it is."""
    for number, match in enumerate(_BLOCK.finditer(text), 1):
        yield f"{where}#{number}", dedent(match[1])


def _documents() -> Iterator[tuple[str, str]]:
    """Yield every example the package's prose carries."""
    pages = [_PACKAGE / "README.md", *sorted(_SOURCE.glob(".agents/skills/*/**/*.md"))]
    for page in pages:
        yield from _blocks(page.read_text(encoding="utf-8"), page.relative_to(_PACKAGE).as_posix())


def _docstrings() -> Iterator[tuple[str, str]]:
    """Yield every example the package's modules, classes and functions carry."""
    for module in sorted(_SOURCE.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        wanted = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        for node in ast.walk(tree):
            if not isinstance(node, wanted):
                continue
            text = ast.get_docstring(node)
            if text is None:
                continue
            name = getattr(node, "name", module.stem)
            where = f"{module.relative_to(_PACKAGE).as_posix()}:{name}"
            yield from _blocks(text, where)


_EXAMPLES = [*_documents(), *_docstrings()]


def test_the_readme_and_the_skill_both_contribute_examples() -> None:
    # A guard on the collector: a change to the fence pattern that quietly
    # matched nothing would leave every example unrun, and green.
    where = {name.split("#")[0] for name, _ in _EXAMPLES}

    assert "README.md" in where
    assert any(name.endswith("SKILL.md") for name in where)
    assert any(name.startswith("src/") for name in where)


@pytest.mark.parametrize("example", [pytest.param(code, id=where) for where, code in _EXAMPLES])
def test_an_example_runs(example: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # An example that writes a file writes it where a test may: it names a
    # path of its own, which is read against the working directory.
    monkeypatch.chdir(tmp_path)

    # Running the example is the whole point: a block that no longer works is
    # documentation that lies, and nothing short of executing it tells us.
    exec(compile(example, "<example>", "exec"), {"__name__": "__example__"})  # noqa: S102
