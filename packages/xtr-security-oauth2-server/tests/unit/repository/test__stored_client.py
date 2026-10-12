"""Finding the stored client a protocol entity names, and refusing to guess."""

from __future__ import annotations

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity
from tests.support.models import client_model
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.repository._stored_client import stored_client_of

pytestmark = pytest.mark.anyio

__all__ = []


async def test_it_returns_the_stored_client_when_found() -> None:
    """Given: a client manager with a stored client.

    When: stored_client_of is called with an entity naming that client.

    Then: the stored client is returned.
    """
    manager = ClientManager(RecordingEventDispatcher())
    stored = client_model(identifier="client-1")
    await manager.save(stored)

    entity = client_entity(identifier="client-1")

    result = await stored_client_of(manager, entity)

    assert result.get_identifier() == "client-1"


async def test_it_raises_when_no_client_is_stored() -> None:
    """Given: a client manager with no stored client.

    When: stored_client_of is called with an entity naming a missing client.

    Then: InvalidArgumentError is raised, naming the identifier.
    """
    manager = ClientManager(RecordingEventDispatcher())
    entity = client_entity(identifier="missing-client")

    with pytest.raises(InvalidArgumentError, match="missing-client"):
        _ = await stored_client_of(manager, entity)
