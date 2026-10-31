"""The bundle module exports the bundle, its configuration, its pass and its tags."""

from __future__ import annotations

from xtr_serializer import bundle


def test_every_exported_name_resolves() -> None:
    assert [name for name in bundle.__all__ if not hasattr(bundle, name)] == []


def test_the_tags_are_named_after_the_bundle() -> None:
    assert (bundle.NORMALIZER_TAG, bundle.ENCODER_TAG) == (
        "serializer.normalizer",
        "serializer.encoder",
    )
