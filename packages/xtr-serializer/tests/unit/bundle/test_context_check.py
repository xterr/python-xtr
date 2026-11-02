"""A configured default context is keyed by strings, as every call's context is."""

from __future__ import annotations

import pytest

from xtr_serializer.bundle._context_check import check_context
from xtr_serializer.exception import InvalidArgumentError


def test_a_context_keyed_by_strings_passes() -> None:
    check_context({"strict": True, "": None}, "the default context")


def test_a_key_that_is_not_a_string_is_refused_naming_the_context() -> None:
    with pytest.raises(InvalidArgumentError, match="the default context"):
        check_context({1: "one"}, "the default context")


def test_a_context_that_is_not_a_mapping_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="a mapping"):
        check_context(["strict"], "the default context")
