"""The work every client here does before a connection is opened."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, Self

from typing_extensions import Unpack
from xtr_http_client_contracts import OPTIONS_DEFAULTS

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal import option_merge
from xtr_http_client.internal.debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import RequestOptions

__all__ = ["HttpClientMixin"]

_AUTH_BASIC_PARTS: Final = (1, 2)
_UNPRINTABLE: Final = re.compile(r"[^\x21-\x7E]")
_NO_BODY: Final = (None, b"", "")


class HttpClientMixin:
    """What a client refuses, and the options it starts every request from.

    Mixed into every client here, so all of them keep their defaults the same
    way and refuse the same requests — which is what lets one be swapped for
    another without a caller noticing. A client is then only the part that
    opens connections.

    Its own state is the one thing a client needs from it: the options every
    request starts from. ``__init__`` takes them so a subclass can hand over
    what it was built with and get back the merged defaults.

    The checks are exposed one by one because a client makes them one at a
    time: the method is known before the options are read, and a client
    preparing its own defaults has no method to check at all.
    """

    __slots__: tuple[str, ...] = ("_default_options",)

    _default_options: dict[str, object]

    def __init__(self, default_options: RequestOptions | None = None) -> None:
        """Start from the contract's defaults, with ``default_options`` over them.

        Raises:
            InvalidArgumentError: When an option is not one this client knows.
        """
        self._default_options = dict(OPTIONS_DEFAULTS)
        if default_options:
            self._default_options = self.merge_default_options(
                default_options,
                self._default_options,
            )

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """A copy of this client whose defaults have ``options`` over them.

        A copy rather than a change, so a caller can narrow a client for one
        job — a header, a timeout, a base URI — without the client everyone
        else holds changing under them.

        Raises:
            InvalidArgumentError: When an option is not one this client knows.
        """
        clone = copy.copy(self)
        # The clone is this very class, and its defaults are the one thing
        # about it that has to change; there is no other way to seed them.
        clone._default_options = self.merge_default_options(  # noqa: SLF001 — same class
            options,
            self._default_options,
        )

        return clone

    @classmethod
    def merge_default_options(
        cls,
        options: Mapping[str, object],
        default_options: Mapping[str, object],
        *,
        allow_extra_options: bool = False,
    ) -> dict[str, object]:
        """Merge what a request asked for over what the client always asks for.

        See :func:`xtr_http_client.internal.option_merge.merge_default_options`.
        """
        return option_merge.merge_default_options(
            cls.__qualname__,
            options,
            default_options,
            allow_extra_options=allow_extra_options,
        )

    def validate_options(self, options: Mapping[str, object]) -> None:
        """Refuse an option this client does not know, naming the closest it does.

        See :func:`xtr_http_client.internal.option_merge.validate_options`.
        """
        option_merge.validate_options(type(self).__qualname__, options, self._default_options)

    @staticmethod
    def validate_method(method: str) -> None:
        """Refuse a method no server would read as the one that was meant.

        Raises:
            InvalidArgumentError: When the method is empty, or is anything
                other than uppercase ASCII letters.
        """
        if method == "":
            raise InvalidArgumentError("The HTTP method cannot be empty.")
        if not (method.isascii() and method.isalpha() and method.isupper()):
            raise InvalidArgumentError(
                f'Invalid HTTP method "{method}", only uppercase letters are accepted.'
            )

    @staticmethod
    def validate_auth(options: Mapping[str, object]) -> None:
        """Refuse credentials this client cannot send, or two sets of them.

        Raises:
            InvalidArgumentError: When ``auth_basic`` or ``auth_bearer`` is
                not of a shape credentials can be read from, or both are set.
        """
        basic = options.get("auth_basic")
        if isinstance(basic, Sequence) and not isinstance(basic, str):
            if len(basic) not in _AUTH_BASIC_PARTS:
                raise InvalidArgumentError(
                    f'Option "auth_basic" must contain 1 or 2 elements, "{len(basic)}" given.'
                )
        elif basic is not None and not isinstance(basic, str):
            raise InvalidArgumentError(
                f'Option "auth_basic" must be a string or a tuple, "{debug_type(basic)}" given.'
            )

        bearer = options.get("auth_bearer")
        if bearer is not None:
            HttpClientMixin._validate_bearer(bearer)
        if basic is not None and bearer is not None:
            raise InvalidArgumentError(
                'Define either the "auth_basic" or the "auth_bearer" option, '
                "setting both is not supported."
            )

    @staticmethod
    def validate_body(options: Mapping[str, object]) -> None:
        """Refuse a request that says what to send twice.

        A JSON document and a body are both the whole body, so a request
        carrying each has not said which one to send.

        Raises:
            InvalidArgumentError: When ``json`` and ``body`` are both set.
        """
        if options.get("json") is None:
            return
        if options.get("body") not in _NO_BODY:
            raise InvalidArgumentError(
                'Define either the "json" or the "body" option, setting both is not supported.'
            )

    @staticmethod
    def _validate_bearer(bearer: object) -> None:
        if not isinstance(bearer, str):
            raise InvalidArgumentError(
                f'Option "auth_bearer" must be a string, "{debug_type(bearer)}" given.'
            )
        if _UNPRINTABLE.search(bearer):
            raise InvalidArgumentError(
                f'Invalid character found in option "auth_bearer": {json.dumps(bearer)}.'
            )
