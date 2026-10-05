from __future__ import annotations

from xtr_recipes.exception import InvalidManifestError, RecipesError


def test_it_derives_from_the_base_and_value_error() -> None:
    assert issubclass(InvalidManifestError, RecipesError)
    assert issubclass(InvalidManifestError, ValueError)


def test_it_keeps_the_package_key_and_reason() -> None:
    error = InvalidManifestError("xtr-messenger", "bundles.foo", "bad")

    assert error.package == "xtr-messenger"
    assert error.key == "bundles.foo"
    assert error.reason == "bad"


def test_its_message_names_all_three() -> None:
    message = str(InvalidManifestError("xtr-messenger", "the-key", "the-reason"))

    assert "xtr-messenger" in message
    assert "the-key" in message
    assert "the-reason" in message
