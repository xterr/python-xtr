"""The fake ``magic`` module keeps the part of python-magic's contract the guesser relies on."""

from __future__ import annotations

from types import ModuleType

import pytest

from tests.support.fake_magic_module import FakeMagicError, FakeMagicModule


def test_it_is_a_module_named_magic() -> None:
    fake = FakeMagicModule("image/gif")

    assert isinstance(fake, ModuleType)
    assert fake.__name__ == "magic"


def test_it_answers_the_type_it_was_built_with_and_records_the_call() -> None:
    fake = FakeMagicModule("image/gif")

    assert fake.from_file("picture", mime=True) == "image/gif"
    assert fake.calls == [("picture", True)]


def test_it_raises_the_error_it_was_built_with() -> None:
    fake = FakeMagicModule(FakeMagicError("no valid magic files"))

    with pytest.raises(FakeMagicError, match="no valid magic files"):
        _ = fake.from_file("picture", mime=True)
