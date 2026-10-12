"""The answer a device gets when it asks to be authorized elsewhere."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

from .abstract_response_type import AbstractResponseType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )

__all__ = ["DeviceCodeResponse"]

_NO_DEVICE_CODE = (
    "This device code response holds no device code; the grant answering the device "
    "authorization request sets one with set_device_code_entity() before the answer is built."
)


class DeviceCodeResponse(AbstractResponseType):
    """Tells a device what to poll with, and where to send its owner.

    A device with no keyboard cannot run an authorization request, so it asks
    for two codes instead: one only it holds and polls the token endpoint with,
    and a short one its owner reads off the screen and types into the
    verification URI on a phone. This is the answer carrying both.

    Two of the fields are optional, because they are of no use to every device.
    The pre-filled verification URI saves an owner typing the code at all —
    useful when the device can show a QR code, pointless when it can only print
    a line of text — and the polling interval is only worth sending when a
    deployment wants its devices to know it rather than guess.

    The clock is taken rather than read from the system because the answer says
    how many seconds are left, and a deployment that freezes or offsets time
    must have that answer follow.
    """

    def __init__(self, clock: ClockInterface) -> None:
        """Answer against ``clock``, which decides how long the codes have left."""
        self._clock: ClockInterface = clock
        self._device_code_entity: DeviceCodeEntityInterface | None = None
        self._include_verification_uri_complete: bool = False
        self._include_interval: bool = False

    def set_device_code_entity(self, device_code_entity: DeviceCodeEntityInterface) -> None:
        """Answer with ``device_code_entity``, the pair of codes just issued."""
        self._device_code_entity = device_code_entity

    def include_verification_uri_complete(self) -> None:
        """Also send the verification URI with the user code already in it."""
        self._include_verification_uri_complete = True

    def include_interval(self) -> None:
        """Also tell the device how many seconds to wait between polls."""
        self._include_interval = True

    def get_extra_params(self) -> Mapping[str, object]:
        """Return the fields this answer carries besides the ones the flow defines.

        Nothing by default. A deployment that has something more to tell its
        devices overrides this rather than the whole answer, so the fields the
        flow defines keep being built here. What it has to say about is read
        off :meth:`_device_code_or_fail`, which is set by then.
        """
        return {}

    @override
    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer the two codes, where to go, and how long they last.

        Raises:
            InvalidArgumentError: When no device code was set, which would
                otherwise answer a device that was issued nothing.
        """
        device_code = self._device_code_or_fail()
        left = device_code.get_expiry_date_time().timestamp() - self._clock.now().timestamp()
        params: dict[str, object] = dict(self.get_extra_params())
        params.update(
            {
                "device_code": device_code.get_identifier(),
                "user_code": device_code.get_user_code(),
                "verification_uri": device_code.get_verification_uri(),
                "expires_in": int(left),
            }
        )
        if self._include_verification_uri_complete:
            params["verification_uri_complete"] = device_code.get_verification_uri_complete()
        if self._include_interval:
            params["interval"] = device_code.get_interval()

        answer = (
            response.with_status(200)
            .with_header("pragma", "no-cache")
            .with_header("cache-control", "no-store")
            .with_header("content-type", "application/json; charset=UTF-8")
        )
        _ = answer.get_body().write(json.dumps(params).encode())

        return answer

    def _device_code_or_fail(self) -> DeviceCodeEntityInterface:
        """Return the device code this answer was given.

        Raises:
            InvalidArgumentError: When none was, which means the answer is
                being built before the codes were issued.
        """
        if self._device_code_entity is None:
            raise InvalidArgumentError(_NO_DEVICE_CODE)

        return self._device_code_entity
