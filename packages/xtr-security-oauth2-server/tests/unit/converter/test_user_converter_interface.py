"""The shipped user converter satisfies the contract the bridge goes through."""

from __future__ import annotations

from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.converter.user_converter_interface import UserConverterInterface


def test_the_shipped_converter_satisfies_it() -> None:
    assert isinstance(UserConverter(), UserConverterInterface)
