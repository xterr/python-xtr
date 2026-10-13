"""The offline-token interface is a mark, read from a token's class hierarchy."""

from __future__ import annotations

from inspect import getmro
from typing import final

from xtr_security_core.authentication.token import AbstractToken, NullToken
from xtr_security_core.authentication.token.offline_token_interface import (
    OfflineTokenInterface,
)
from xtr_security_core.authentication.token.token_interface import TokenInterface


@final
class _Offline(AbstractToken, OfflineTokenInterface):
    __slots__ = ()


def test_it_extends_the_token_interface() -> None:
    assert TokenInterface in getmro(OfflineTokenInterface)


def test_a_token_declaring_it_carries_the_mark() -> None:
    assert OfflineTokenInterface in type(_Offline()).__mro__


def test_a_token_not_declaring_it_does_not_carry_the_mark() -> None:
    assert OfflineTokenInterface not in type(AbstractToken()).__mro__
    assert OfflineTokenInterface not in type(NullToken()).__mro__
