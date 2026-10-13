"""A scripted answer whose body is a JSON document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final, Self, cast, final

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.mock_head import response_header_lines

from .mock_response import MockResponse

if TYPE_CHECKING:
    from collections.abc import Mapping
    from os import PathLike

__all__ = ["JsonMockResponse"]

_JSON: Final = "application/json"


@final
class JsonMockResponse(MockResponse):
    """A written answer carrying a value encoded as JSON, labelled as JSON.

    The one thing a JSON answer adds to a scripted one: the body is a value
    rather than bytes, and the content type says what it is — unless the
    script named one of its own, which a test does to answer with a problem
    document.

    ```python
    client = MockHttpClient(JsonMockResponse({"id": 7}, {"http_code": 201}))
    async with await client.request("GET", "/orders") as response:
        assert await response.to_array() == {"id": 7}
    ```
    """

    __slots__ = ()

    def __init__(
        self,
        body: object = None,
        info: Mapping[str, object] | None = None,
    ) -> None:
        """Write out an answer carrying ``body`` as JSON.

        Args:
            body: Any value JSON can be made of. It is encoded as it stands,
                so ``None`` is the document ``null``.
            info: What the transfer is to claim about itself, as
                :class:`MockResponse` takes it. A ``content-type`` among its
                ``response_headers`` is left alone; one is added when there is
                none.

        Raises:
            InvalidArgumentError: When the value cannot be encoded as JSON.
        """
        super().__init__(_encoded(body), _labelled(info))

    @classmethod
    def from_file(
        cls,
        path: str | PathLike[str],
        info: Mapping[str, object] | None = None,
    ) -> Self:
        """Write out an answer carrying the JSON document a file holds.

        The file is read now rather than when the response is issued, so a
        test that names the wrong file is told so where it named it.

        Args:
            path: The file to read.
            info: What the transfer is to claim about itself.

        Returns:
            The response, carrying the document the file holds.

        Raises:
            InvalidArgumentError: When there is no such file, or what it holds
                is not JSON.
        """
        file = Path(path)
        if not file.is_file():
            raise InvalidArgumentError(f'File not found: "{path}".')

        try:
            document = cast("object", json.loads(file.read_text(encoding="utf-8")))
        except ValueError as error:
            raise InvalidArgumentError(f'File "{path}" does not contain valid JSON.') from error

        return cls(document, info)


def _encoded(body: object) -> str:
    """``body`` as the JSON document it is to be sent as.

    Raises:
        InvalidArgumentError: When the value cannot be encoded as JSON. The
            answer is refused where it is written, rather than failing later
            as a transfer that produced nothing.
    """
    try:
        return json.dumps(body)
    except (TypeError, ValueError) as error:
        raise InvalidArgumentError(f"JSON encoding failed: {error}") from error


def _labelled(info: Mapping[str, object] | None) -> dict[str, object]:
    """``info`` with a JSON content type, unless it already names one."""
    script = dict(info or {})
    lines = response_header_lines(script.get("response_headers"))

    if not any(line.lower().startswith("content-type:") for line in lines):
        script["response_headers"] = [*lines, f"Content-Type: {_JSON}"]

    return script
