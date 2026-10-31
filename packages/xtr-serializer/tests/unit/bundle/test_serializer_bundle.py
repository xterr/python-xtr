"""The bundle registers a serializer per name, reachable under every interface it implements."""

from __future__ import annotations

import pytest
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_dependency_injection.testing import assert_zero_config

from tests.support.application_bundle import Registration, serializer_kernel
from tests.support.shapes import Point
from xtr_serializer import (
    DecoderInterface,
    DenormalizerInterface,
    EncoderInterface,
    NormalizerInterface,
    Serializer,
    SerializerInterface,
)
from xtr_serializer.bundle import (
    ENCODER_TAG,
    NORMALIZER_TAG,
    NamedSerializerConfig,
    SerializerBundle,
    SerializerConfig,
)
from xtr_serializer.exception import InvalidArgumentError

pytestmark = pytest.mark.anyio

INTERFACES = (
    SerializerInterface,
    NormalizerInterface,
    DenormalizerInterface,
    EncoderInterface,
    DecoderInterface,
)


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(SerializerBundle)


async def test_the_default_serializer_is_every_interface_it_implements() -> None:
    async with await serializer_kernel().boot() as booted:
        serializer = await booted.container.get(Serializer)
        found = [await booted.container.get(interface) for interface in INTERFACES]

    assert all(one is serializer for one in found)


async def test_the_default_serializer_round_trips_a_dataclass() -> None:
    async with await serializer_kernel().boot() as booted:
        serializer = await booted.container.get(SerializerInterface)

    assert serializer.deserialize(serializer.serialize(Point(1, 2), "json"), Point, "json") == (
        Point(1, 2)
    )


async def test_a_named_serializer_is_every_interface_under_its_name() -> None:
    config = SerializerConfig(named_serializers={"api": NamedSerializerConfig()})

    async with await serializer_kernel(config).boot() as booted:
        default = await booted.container.get(Serializer)
        api = await booted.container.get(Serializer, "api")
        found = [await booted.container.get(interface, "api") for interface in INTERFACES]

    assert api is not default
    assert all(one is api for one in found)


@pytest.mark.parametrize("tag", [NORMALIZER_TAG, ENCODER_TAG])
async def test_a_service_tagged_as_what_it_is_not_fails_the_boot(tag: str) -> None:
    kernel = serializer_kernel(None, Registration(Point(0, 0), None, tag))

    with pytest.raises(ServiceResolutionError) as raised:
        _ = await kernel.boot()

    assert isinstance(raised.value.__cause__, InvalidArgumentError)
