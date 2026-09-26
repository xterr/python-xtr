"""The clock: its base arrives from the fulltext config's ``AliasOf`` field.

``FulltextConfig.clock`` is ``Annotated[ClockConfig | None, AliasOf("clock")]``; the value
set in ``bookshop.config.fulltext`` is forwarded here as the clock's base (step 3). An
application base provider for ``ClockConfig`` as well would be a
``ConflictingConfigProvidersError`` naming both — so this module only *transforms*.
"""

from __future__ import annotations

from dataclasses import replace

from xtr_clock.bundle import ClockConfig
from xtr_dependency_injection import configure, when

__all__ = ["clock_in_prod"]


@configure
@when("prod")
def clock_in_prod(config: ClockConfig) -> ClockConfig:
    """In prod, report every instant in UTC, whatever ``APP_TIMEZONE`` says."""
    return replace(config, timezone="UTC")
