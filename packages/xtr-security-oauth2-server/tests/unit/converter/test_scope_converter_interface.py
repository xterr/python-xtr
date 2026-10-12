"""The shipped scope converter satisfies the contract the bridges go through."""

from __future__ import annotations

from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.converter.scope_converter_interface import ScopeConverterInterface


def test_the_shipped_converter_satisfies_it() -> None:
    assert isinstance(ScopeConverter(), ScopeConverterInterface)
