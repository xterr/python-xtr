"""The pattern helper compiles a matcher's regular expression, or refuses it."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.request_matcher._pattern import compile_pattern


def test_it_compiles_a_valid_pattern() -> None:
    compiled = compile_pattern(r"^/api", "path")

    assert compiled.search("/api/books") is not None


def test_it_refuses_a_bad_pattern_naming_the_field() -> None:
    with pytest.raises(InvalidArgumentError, match="host"):
        _ = compile_pattern(r"^/(api", "host")
