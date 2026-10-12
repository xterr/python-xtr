from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_remote_event import PayloadConverterInterface, RemoteEvent

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _Converter:
    """Reads the two fields it needs out of a payload it understands."""

    def convert(self, payload: Mapping[str, object]) -> RemoteEvent:
        return RemoteEvent(str(payload["type"]), str(payload["id"]), dict(payload))


@final
class _WithoutConvert:
    """Turns payloads into events under another name, so it is not a converter."""

    def parse(self, payload: Mapping[str, object]) -> RemoteEvent:
        return RemoteEvent("payment.captured", str(payload["id"]), dict(payload))


def test_a_converter_with_the_method_satisfies_the_contract() -> None:
    converter: PayloadConverterInterface = _Converter()

    assert isinstance(converter, PayloadConverterInterface)


def test_a_class_without_the_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutConvert(), PayloadConverterInterface)
