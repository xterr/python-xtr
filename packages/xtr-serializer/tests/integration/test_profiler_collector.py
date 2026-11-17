"""With the http kernel profiling, every serializer is traced and its panel joins the profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final, override

import pytest
from xtr_dependency_injection import Bundle, Kernel, NoConfig, as_bundle
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import DataCollectorTemplates, ProfiledRequest
from xtr_http_kernel.profiler import Profiler
from xtr_http_message import ServerRequest

from tests.support.shapes import Point
from xtr_serializer import (
    DecoderInterface,
    DenormalizerInterface,
    EncoderInterface,
    NormalizerInterface,
    NotEncodableValueError,
    Serializer,
    SerializerInterface,
)
from xtr_serializer.bundle import NamedSerializerConfig, SerializerBundle, SerializerConfig
from xtr_serializer.data_collector import (
    SerializerCall,
    SerializerDataCollector,
    TraceableSerializer,
)

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

pytestmark = pytest.mark.anyio


@final
@as_bundle("application")
class _ApplicationBundle(Bundle[NoConfig]):
    """Names one serializer beside the default one."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        builder.prepend_extension_config(
            "serializer",
            lambda _default: SerializerConfig(named_serializers={"api": NamedSerializerConfig()}),
        )

    @override
    def load_extension(
        self, config: NoConfig, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, services, builder


@pytest.fixture(autouse=True)
def _folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        "xtr_serializer.bundle",
        env="test",
        bundles={
            SerializerBundle: {"all": True},
            HttpKernelBundle: {"all": True},
            _ApplicationBundle: {"all": True},
        },
        resources=resources,
    )


def _profiled() -> ProfiledRequest:
    return ProfiledRequest(ServerRequest("GET", "http://app.test/"), 200, {}, {})


async def test_with_the_profiler_on_the_collector_joins_with_its_template() -> None:
    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        profiler = await booted.container.get(Profiler)
        templates = await booted.container.get(DataCollectorTemplates)

    assert profiler.has("serializer")
    assert isinstance(profiler.get("serializer"), SerializerDataCollector)
    assert templates.template_of("serializer") == "@xtr_serializer/collector/serializer.html.j2"


async def test_every_interface_of_every_serializer_gives_the_traced_one() -> None:
    interfaces = (
        SerializerInterface,
        NormalizerInterface,
        DenormalizerInterface,
        EncoderInterface,
        DecoderInterface,
    )

    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        default = [await booted.container.get(interface) for interface in interfaces]
        api = [await booted.container.get(interface, "api") for interface in interfaces]

    assert isinstance(default[0], TraceableSerializer)
    assert isinstance(api[0], TraceableSerializer)
    assert api[0] is not default[0]
    assert all(one is default[0] for one in default)
    assert all(one is api[0] for one in api)


async def test_the_serializer_class_itself_is_still_the_untraced_one() -> None:
    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        serializer = await booted.container.get(Serializer, "api")

    assert type(serializer) is Serializer


async def test_the_calls_of_a_profiled_request_are_collected() -> None:
    async with await _kernel("tests.fixtures.profiler_on").boot() as booted:
        collector = await booted.container.get(SerializerDataCollector)
        default = await booted.container.get(SerializerInterface)
        api = await booted.container.get(SerializerInterface, "api")
        collector.begin_request()

        written = default.serialize(Point(1, 2), "json", {"json_indent": 2})
        _ = api.deserialize(written, Point, "json")
        with pytest.raises(NotEncodableValueError):
            _ = api.deserialize("nope", Point, "json")
        early = collector.collect(_profiled())
        data = collector.late_collect(early, _profiled())

    calls = cast("list[SerializerCall]", data["calls"])
    assert [(call["serializer"], call["method"], call["target_type"]) for call in calls] == [
        ("default", "serialize", None),
        ("api", "deserialize", "Point"),
        ("api", "deserialize", "Point"),
    ]
    assert calls[0]["context"] == ["json_indent"]
    assert calls[2]["error"] is not None
    assert calls[2]["error"]["class"] == "NotEncodableValueError"
    assert data["count"] == 3
    assert data["errors"] == 1
    assert data["by_method"] == {"serialize": 1, "deserialize": 2}
    assert data["duration_ms"] == sum(call["duration_ms"] for call in calls)


async def test_with_the_profiler_off_nothing_is_traced_or_collected() -> None:
    async with await _kernel().boot() as booted:
        serializer = await booted.container.get(SerializerInterface)
        registered = booted.container.has(SerializerDataCollector)

    assert not registered
    assert isinstance(serializer, Serializer)
