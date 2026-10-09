"""A URI that satisfies the contract and carries no component."""

from __future__ import annotations

from typing import Self

from typing_extensions import override

__all__ = ["FakeUri"]


class FakeUri:
    """Answers every question on the URI contract, with every component empty.

    Each ``with_*`` answers with the same instance, which an immutable value
    with nothing in it may: there is no state to keep apart.
    """

    def get_scheme(self) -> str:
        return ""

    def get_authority(self) -> str:
        return ""

    def get_user_info(self) -> str:
        return ""

    def get_host(self) -> str:
        return ""

    def get_port(self) -> int | None:
        return None

    def get_path(self) -> str:
        return ""

    def get_query(self) -> str:
        return ""

    def get_fragment(self) -> str:
        return ""

    def with_scheme(self, scheme: str) -> Self:
        del scheme
        return self

    def with_user_info(self, user: str, password: str | None = None) -> Self:
        del user, password
        return self

    def with_host(self, host: str) -> Self:
        del host
        return self

    def with_port(self, port: int | None) -> Self:
        del port
        return self

    def with_path(self, path: str) -> Self:
        del path
        return self

    def with_query(self, query: str) -> Self:
        del query
        return self

    def with_fragment(self, fragment: str) -> Self:
        del fragment
        return self

    @override
    def __str__(self) -> str:
        return ""
