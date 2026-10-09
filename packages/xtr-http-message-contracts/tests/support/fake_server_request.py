"""A server request that satisfies the contract and arrived with nothing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tests.support.fake_request import FakeRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["FakeServerRequest"]


class FakeServerRequest(FakeRequest):
    """Answers the server request contract on top of :class:`FakeRequest`."""

    def get_server_params(self) -> Mapping[str, object]:
        return {}

    def get_cookie_params(self) -> Mapping[str, str]:
        return {}

    def with_cookie_params(self, cookies: Mapping[str, str]) -> Self:
        del cookies
        return self

    def get_query_params(self) -> Mapping[str, object]:
        return {}

    def with_query_params(self, query: Mapping[str, object]) -> Self:
        del query
        return self

    def get_uploaded_files(self) -> Mapping[str, object]:
        return {}

    def with_uploaded_files(self, uploaded_files: Mapping[str, object]) -> Self:
        del uploaded_files
        return self

    def get_parsed_body(self) -> object | None:
        return None

    def with_parsed_body(self, data: object | None) -> Self:
        del data
        return self

    def get_attributes(self) -> Mapping[str, object]:
        return {}

    def get_attribute(self, name: str, default: object | None = None) -> object | None:
        del name
        return default

    def with_attribute(self, name: str, value: object) -> Self:
        del name, value
        return self

    def without_attribute(self, name: str) -> Self:
        del name
        return self
