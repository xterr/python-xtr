"""The shipped client is the abstract one made concrete, and nothing more."""

from __future__ import annotations

from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.model.client import Client


def test_it_is_an_abstract_client() -> None:
    assert isinstance(Client("Name", "client-1", None), AbstractClient)


def test_it_is_built_from_the_three_things_a_client_is_registered_with() -> None:
    client = Client("Name", "client-1", "hashed")

    assert (client.get_name(), client.get_identifier(), client.get_secret()) == (
        "Name",
        "client-1",
        "hashed",
    )
