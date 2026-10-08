from __future__ import annotations

from pathlib import Path

from xtr_cli import ScaffoldPlan


def test_a_plan_renders_a_line_per_file_then_per_command() -> None:
    plan = ScaffoldPlan(
        directory=Path("shop"),
        files=(("pyproject.toml", ""), ("src/shop/kernel.py", "")),
        commands=(("uv", "add", "--", "xtr-console[di]>=3.0,<4"),),
        next_steps=(),
    )

    assert plan.render() == (
        "write pyproject.toml",
        "write src/shop/kernel.py",
        "run   uv add -- 'xtr-console[di]>=3.0,<4'",
    )
