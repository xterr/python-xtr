"""The answer a device gets when it asks to be authorized."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.entities import DeviceCode, make_client
from tests.support.messages import document_of
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.response_types.device_code_response import DeviceCodeResponse
from xtr_security_oauth2_server_core.response_types.response_type_interface import (
    ResponseTypeInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_VERIFICATION_URI = "https://example.com/device"


def _device_code() -> DeviceCode:
    code = DeviceCode()
    code.set_identifier("device-1")
    code.set_user_code("BCDFGHJK")
    code.set_verification_uri(_VERIFICATION_URI)
    code.set_expiry_date_time(FROZEN_NOW + timedelta(minutes=10))
    code.set_interval(5)
    code.set_client(make_client())

    return code


async def _answered(response_type: DeviceCodeResponse) -> Mapping[str, object]:
    return cast(
        "Mapping[str, object]",
        await document_of(await response_type.generate_http_response(Response())),
    )


@final
class _ResponseWithAnExtraField(DeviceCodeResponse):
    """A response type an add-on would write to carry a field of its own."""

    @override
    def get_extra_params(self) -> Mapping[str, object]:
        return {"polling_hint": self._device_code_or_fail().get_interval() * 2}


@final
class _ResponseWithShadowingExtras(DeviceCodeResponse):
    """A response type that tries to override a flow field."""

    @override
    def get_extra_params(self) -> Mapping[str, object]:
        return {"device_code": "x", "extra": 1}


def test_it_satisfies_the_response_type_contract() -> None:
    assert isinstance(DeviceCodeResponse(make_clock()), ResponseTypeInterface)


@pytest.mark.anyio
async def test_it_names_the_device_code_the_user_code_and_where_to_type_it() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.set_device_code_entity(_device_code())

    body = await _answered(response_type)

    assert body["device_code"] == "device-1"
    assert body["user_code"] == "BCDFGHJK"
    assert body["verification_uri"] == _VERIFICATION_URI


@pytest.mark.anyio
async def test_it_counts_the_seconds_left_from_the_clock_it_was_given() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.set_device_code_entity(_device_code())

    assert (await _answered(response_type))["expires_in"] == 600


@pytest.mark.anyio
async def test_it_leaves_out_the_pre_filled_uri_and_the_interval_by_default() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.set_device_code_entity(_device_code())

    body = await _answered(response_type)

    assert "verification_uri_complete" not in body
    assert "interval" not in body


@pytest.mark.anyio
async def test_it_carries_the_pre_filled_uri_when_asked_to() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.include_verification_uri_complete()
    response_type.set_device_code_entity(_device_code())

    expected = f"{_VERIFICATION_URI}?user_code=BCDFGHJK"

    assert (await _answered(response_type))["verification_uri_complete"] == expected


@pytest.mark.anyio
async def test_it_carries_the_polling_interval_when_asked_to() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.include_interval()
    response_type.set_device_code_entity(_device_code())

    assert (await _answered(response_type))["interval"] == 5


@pytest.mark.anyio
async def test_it_answers_json_that_nothing_may_cache() -> None:
    response_type = DeviceCodeResponse(make_clock())
    response_type.set_device_code_entity(_device_code())

    answer = await response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("pragma") == "no-cache"
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"


@pytest.mark.anyio
async def test_a_subclass_adds_fields_of_its_own() -> None:
    response_type = _ResponseWithAnExtraField(make_clock())
    response_type.set_device_code_entity(_device_code())

    assert (await _answered(response_type))["polling_hint"] == 10


@pytest.mark.anyio
async def test_answering_before_a_device_code_is_set_names_the_setter() -> None:
    response_type = DeviceCodeResponse(make_clock())

    with pytest.raises(InvalidArgumentError, match="set_device_code_entity"):
        _ = await response_type.generate_http_response(Response())


@pytest.mark.anyio
async def test_it_preserves_flow_fields_when_extras_try_to_override_them() -> None:
    response_type = _ResponseWithShadowingExtras(make_clock())
    response_type.set_device_code_entity(_device_code())

    body = await _answered(response_type)
    assert body["device_code"] == "device-1"
    assert body["extra"] == 1
