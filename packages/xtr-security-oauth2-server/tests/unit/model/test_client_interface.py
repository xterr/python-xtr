"""The shipped client satisfies the contract a manager stores clients through."""

from __future__ import annotations

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.client_interface import ClientInterface


def test_the_shipped_client_satisfies_it() -> None:
    assert isinstance(Client("Name", "client-1", None), ClientInterface)
