"""What the security panel never shows: a value kept under a name like a credential's."""

from __future__ import annotations

from typing import Final, cast

from xtr_http_kernel.data_collector import clone_var

__all__ = ["MASK", "masked"]

MASK: Final = "******"

_SENSITIVE_WORDS: Final = ("password", "secret", "token", "passwd", "api_key", "apikey")


def masked(node: dict[str, object]) -> dict[str, object]:
    """Return ``node`` — a :func:`clone_var` tree — with every credential-like entry masked.

    A passport or a subject carries whatever its authenticator or its caller put
    on it — a password badge, a bearer token in an attribute — and a profile is
    written to disk for anyone with the profiler to read. Whatever sits under a
    key or an attribute named like a credential is replaced by ``******``, at
    every depth the tree was cloned to.
    """
    match node.get("kind"):
        case "mapping":
            pairs = cast("list[tuple[dict[str, object], dict[str, object]]]", node["items"])
            return {
                **node,
                "items": [[key, _masked_under(_key_name(key), value)] for key, value in pairs],
            }
        case "sequence":
            items = cast("list[dict[str, object]]", node["items"])
            return {**node, "items": [masked(item) for item in items]}
        case "object":
            attributes = cast("list[tuple[str, dict[str, object]]]", node["attributes"])
            return {
                **node,
                "attributes": [[name, _masked_under(name, value)] for name, value in attributes],
            }
        case _:
            return node


def _masked_under(name: str | None, node: dict[str, object]) -> dict[str, object]:
    if name is not None and any(word in name.lower() for word in _SENSITIVE_WORDS):
        return clone_var(MASK)
    return masked(node)


def _key_name(key: dict[str, object]) -> str | None:
    value = key.get("value")
    return value if key.get("kind") == "str" and isinstance(value, str) else None
