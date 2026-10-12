from __future__ import annotations

import pytest

from tests.support.consumers import RecordingConsumer
from xtr_remote_event.consumer._built_consumers import BuiltConsumers
from xtr_remote_event.exception import LogicError


@pytest.mark.anyio
async def test_it_hands_back_the_consumer_registered_under_a_name() -> None:
    consumer = RecordingConsumer()

    assert await BuiltConsumers({"stripe": consumer}).get("stripe") is consumer


@pytest.mark.anyio
async def test_it_refuses_a_name_nothing_was_registered_under() -> None:
    with pytest.raises(LogicError) as caught:
        _ = await BuiltConsumers({}).get("mailgun")

    assert str(caught.value) == 'Unable to find a consumer for message of type "mailgun".'


def test_it_knows_which_names_it_has_without_building_anything() -> None:
    built = BuiltConsumers({"stripe": RecordingConsumer()})

    assert built.has("stripe")
    assert not built.has("mailgun")
    assert dict(built.provided_services()) == {"stripe": RecordingConsumer}


@pytest.mark.anyio
async def test_the_mapping_it_was_given_is_copied() -> None:
    consumers = {"stripe": RecordingConsumer()}
    built = BuiltConsumers(consumers)
    consumers.clear()

    assert built.has("stripe")
