"""The makers: classes they write are ``@final``.

Nothing here needs configuring — the makers write into ``kernel.package`` and mark classes
``@final`` by default. It is spelt out to show where a development-only bundle's configuration
belongs: ``xtr_maker`` is imported here, in the ``dev`` folder, and production never imports it.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_maker.bundle import MakerConfig

__all__ = ["maker"]


@configure
def maker() -> MakerConfig:
    """Mark generated classes ``@final``; ``root_package`` stays ``None``, the kernel's package."""
    return MakerConfig(final_classes=True)
