from __future__ import annotations

from xtr_logging.bridge import stdlib


def test_the_bridge_re_exports_the_record_attribute_names() -> None:
    assert stdlib.CHANNEL_ATTR == "xtr_channel"
    assert stdlib.CONTEXT_ATTR == "xtr_context"
    assert stdlib.EXTRA_ATTR == "xtr_extra"
    assert {"CHANNEL_ATTR", "CONTEXT_ATTR", "EXTRA_ATTR"} <= set(stdlib.__all__)
