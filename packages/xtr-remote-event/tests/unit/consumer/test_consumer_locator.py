from __future__ import annotations

import pytest
from xtr_service_contracts import ServiceProviderInterface

from tests.support.consumers import ConsumerProvider, RecordingConsumer
from xtr_remote_event import ConsumerInterface
from xtr_remote_event.consumer import ConsumerLocator
from xtr_remote_event.exception import LogicError


def test_the_fakes_answer_to_the_contracts_they_stand_in_for() -> None:
    assert isinstance(RecordingConsumer(), ConsumerInterface)
    assert isinstance(ConsumerProvider({}), ServiceProviderInterface)


@pytest.mark.anyio
async def test_it_hands_over_a_consumer_given_as_a_mapping() -> None:
    consumer = RecordingConsumer()
    locator = ConsumerLocator({"stripe": consumer})

    assert await locator.get("stripe") is consumer


@pytest.mark.anyio
async def test_it_hands_over_a_consumer_a_provider_builds() -> None:
    consumer = RecordingConsumer()
    locator = ConsumerLocator(ConsumerProvider({"stripe": consumer}))

    assert await locator.get("stripe") is consumer


@pytest.mark.anyio
async def test_it_refuses_a_name_nothing_is_registered_under() -> None:
    locator = ConsumerLocator({"stripe": RecordingConsumer()})

    with pytest.raises(LogicError) as caught:
        _ = await locator.get("mailgun")

    assert str(caught.value) == 'Unable to find a consumer for message of type "mailgun".'


@pytest.mark.anyio
async def test_a_provider_without_the_name_is_refused_before_it_is_asked() -> None:
    locator = ConsumerLocator(ConsumerProvider({}))

    with pytest.raises(LogicError) as caught:
        _ = await locator.get("mailgun")

    assert str(caught.value) == 'Unable to find a consumer for message of type "mailgun".'


def test_it_says_which_names_it_answers_to() -> None:
    locator = ConsumerLocator({"stripe": RecordingConsumer()})

    assert locator.has("stripe")
    assert not locator.has("mailgun")
    assert dict(locator.provided_services()) == {"stripe": RecordingConsumer}
