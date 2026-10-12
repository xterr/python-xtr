"""The marker every storage contract is grouped under."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.repository_interface import RepositoryInterface


@final
class _Nothing:
    """A class that implements no storage contract at all."""


def test_the_client_contract_is_grouped_under_the_marker() -> None:
    assert issubclass(ClientRepositoryInterface, RepositoryInterface)


def test_the_marker_asks_for_nothing() -> None:
    assert isinstance(_Nothing(), RepositoryInterface)
