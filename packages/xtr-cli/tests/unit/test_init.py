from __future__ import annotations

import xtr_cli


def test_every_public_name_is_importable_from_the_package() -> None:
    missing = [name for name in xtr_cli.__all__ if not hasattr(xtr_cli, name)]

    assert missing == []
