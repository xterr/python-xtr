"""A boot hook that exists only in dev and test: ``@when``, repeated."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Autowire, Injected, on_boot, when
from xtr_logging_contracts import LoggerInterface

__all__ = ["describe_development_environment"]


@on_boot
@when("dev")
@when("test")
def describe_development_environment(
    logger: Injected[LoggerInterface],
    project_dir: Annotated[str, Autowire(param="kernel.project_dir")],
) -> None:
    """Only in dev and test — ``@when`` repeated widens the set, like ``@when("dev", "test")``."""
    logger.debug("project directory: {dir}", {"dir": project_dir})
