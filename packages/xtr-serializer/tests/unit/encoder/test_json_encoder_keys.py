"""The JSON encoder's keys are spelled as a context carries them."""

from __future__ import annotations

from xtr_serializer.encoder.json_encoder_keys import JSON_ALLOW_INF_NAN, JSON_INDENT


def test_each_key_is_spelled_as_a_context_carries_it() -> None:
    assert [JSON_INDENT, JSON_ALLOW_INF_NAN] == ["json_indent", "json_allow_inf_nan"]
