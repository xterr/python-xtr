"""A client is about to be stored, and a listener may still change it."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from tests.support.models import client_model
from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(PreSaveClientEvent(client_model()), Event)


def test_it_carries_the_client_about_to_be_stored() -> None:
    client = client_model()

    assert PreSaveClientEvent(client).get_client() is client


def test_a_listener_can_put_another_client_on_it() -> None:
    event = PreSaveClientEvent(client_model("client-1"))
    replacement = client_model("client-2")

    event.set_client(replacement)

    assert event.get_client() is replacement


def test_its_reading_names_the_client_without_its_secret() -> None:
    reading = repr(PreSaveClientEvent(client_model(secret="hashed-secret")))

    assert "hashed-secret" not in reading
    assert reading == "PreSaveClientEvent(client=Client(identifier='client-1'))"
