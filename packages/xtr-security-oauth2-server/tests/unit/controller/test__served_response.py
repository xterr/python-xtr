"""An endpoint answers with the framework's own response, and says so when it cannot."""

from __future__ import annotations

import pytest
from xtr_http_kernel.bridge import Response
from xtr_http_message import Response as MessageOnlyResponse

from xtr_security_oauth2_server.controller._served_response import served
from xtr_security_oauth2_server.exception import InvalidConfigurationError


def test_the_kernels_own_response_is_handed_back_as_it_is() -> None:
    # In an application the message and the response are one object, which is
    # the whole invariant the endpoints rely on.
    answer = Response(200)

    assert served(answer) is answer


def test_a_response_the_framework_cannot_send_is_refused() -> None:
    # A response that is only a message: something has replaced the kernel's
    # registration, and an endpoint handing one back would fail far from here.
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = served(MessageOnlyResponse(200))

    message = str(refused.value)
    assert "Response" in message
    assert "ResponseInterface" in message
