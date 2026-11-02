"""The JSON encoder's key is spelled as an application writes it in a context."""

from __future__ import annotations

from typing import cast

from xtr_serializer.encoder import json_encoder_keys as keys


def test_every_key_is_spelled_as_an_application_writes_it() -> None:
    spellings = {name: cast("object", getattr(keys, name)) for name in keys.__all__}

    assert spellings == {"JSON_INDENT": "json_indent"}
