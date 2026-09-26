"""Services that compile, and fail when built."""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Autowire, as_service

__all__ = ["NeedsANumber", "NeedsAnUnsetVariable"]


@final
@as_service
class NeedsAnUnsetVariable:
    """Reads ``SHOP_PAYROLL_TOKEN``, which is set nowhere.

    Building it raises ``ServiceResolutionError`` caused by
    ``MissingEnvironmentVariableError`` — on first use, not at boot.
    """

    def __init__(self, token: Annotated[str, Autowire(env="SHOP_PAYROLL_TOKEN")]) -> None:
        """Keep ``token``."""
        self.token = token


@final
@as_service
class NeedsANumber:
    """``SHOP_NAME`` is not a number: ``InvalidEnvironmentVariableError`` when built."""

    def __init__(self, count: Annotated[int, Autowire(env="int:SHOP_NAME")]) -> None:
        """Keep ``count``."""
        self.count = count
