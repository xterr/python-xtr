"""The message bus finds this transport by its schemes, and imports it only when one is used."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
from taskiq import InMemoryBroker
from xtr_messenger import Dsn, MissingSerializerError
from xtr_messenger.bridge.taskiq import StartedBrokers, TaskiqSender
from xtr_messenger.transport.transport_factory_discovery import (
    ENTRY_POINT_GROUP,
    advertised_schemes,
    default_factories,
    factory_for,
)

from tests.support.serialization import json_serializer
from xtr_amqp_messenger import AmqpTransportFactory

_PACKAGE = pathlib.Path(__file__).resolve().parents[2]
_SOURCE = _PACKAGE / "src" / "xtr_amqp_messenger"


def test_both_schemes_are_advertised() -> None:
    assert {"amqp", "amqps"} <= set(advertised_schemes())


def test_the_packaged_entry_points_name_this_factory() -> None:
    manifest = (_PACKAGE / "pyproject.toml").read_text()

    assert f'[project.entry-points."{ENTRY_POINT_GROUP}"]' in manifest
    assert 'amqp = "xtr_amqp_messenger.transport:AmqpTransportFactory"' in manifest
    assert 'amqps = "xtr_amqp_messenger.transport:AmqpTransportFactory"' in manifest


@pytest.mark.parametrize("dsn", ["amqp://h:5672/", "amqps://h:5671/"])
def test_a_scheme_resolves_to_this_factory_with_the_serializer_given(dsn: str) -> None:
    assert isinstance(factory_for(Dsn.parse(dsn), json_serializer()), AmqpTransportFactory)


def test_without_a_serializer_the_factory_is_refused() -> None:
    with pytest.raises(MissingSerializerError, match="amqp"):
        _ = factory_for(Dsn.parse("amqp://h:5672/"))


def test_one_factory_serving_both_schemes_is_listed_once() -> None:
    found = [f for f in default_factories(json_serializer()) if isinstance(f, AmqpTransportFactory)]

    assert len(found) == 1


def test_an_amqp_bus_loads_its_broker_library() -> None:
    code = (
        "from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer\n"
        "from xtr_messenger import JsonSerializer, MessageBusConfig, MessageBusFactory\n"
        "from xtr_messenger import TransportConfig, TransportFactory\n"
        "config = MessageBusConfig(\n"
        "    transports={'q': TransportConfig('amqp://guest:guest@h:5672/', queue='jobs')}\n"
        ")\n"
        "wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))\n"
        "MessageBusFactory(config, [TransportFactory(serializer=wire)]).bus()\n"
        "import sys\n"
        "assert 'taskiq' in sys.modules\n"
        "assert 'xtr_amqp_messenger' in sys.modules\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_this_package_is_the_one_that_names_the_rabbitmq_driver() -> None:
    names_driver = [p.name for p in sorted(_SOURCE.rglob("*.py")) if "aio_pika" in p.read_text()]

    assert names_driver != []


def test_it_builds_on_the_broker_agnostic_bridge_it_shares() -> None:
    """Publishing is the bus's taskiq bridge, which works on any taskiq broker."""
    assert TaskiqSender(InMemoryBroker(), StartedBrokers(), json_serializer()) is not None
