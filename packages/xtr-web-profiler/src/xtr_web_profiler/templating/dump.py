"""A value a collector kept, as browsable HTML."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, cast

from markupsafe import Markup, escape

__all__ = ["dump"]

_OPEN_LEVELS: Final = 1


def dump(node: object, depth: int = 0) -> Markup:
    """Return ``node`` — a tree :func:`~xtr_http_kernel.data_collector.clone_var` made — as HTML.

    Mappings, sequences and objects become nested ``<details>``, open on the
    first level; scalars and text are escaped and marked with a class per
    kind. A value that is not such a tree — plain text, a number a collector
    kept as it is — is shown as itself.
    """
    plain = node
    tree = cast("Mapping[str, object] | None", node if isinstance(node, Mapping) else None)
    if tree is None or "kind" not in tree:
        return _scalar(plain)
    kind = tree["kind"]
    type_name = str(tree.get("type", ""))
    if kind == "scalar":
        return _scalar(tree.get("value"), type_name)
    if kind == "str":
        return Markup('<span class="xtr-dump-str" title="{}">"{}"</span>{}').format(
            type_name, tree.get("value", ""), _more(tree)
        )
    if kind == "bytes":
        return Markup("<span class=\"xtr-dump-bytes\">b'{}' ({} bytes)</span>{}").format(
            tree.get("value", ""), tree.get("length", 0), _more(tree)
        )
    if kind == "cut":
        reason = "already shown above" if tree.get("reason") == "recursion" else "too deep"
        return Markup('<span class="xtr-dump-cut" title="{}">{} …</span>').format(reason, type_name)
    return _container(tree, str(kind), type_name, depth)


def _container(tree: Mapping[str, object], kind: str, type_name: str, depth: int) -> Markup:
    if kind == "mapping":
        pairs = cast("Sequence[Sequence[object]]", tree.get("items", ()))
        rows = [
            Markup('<li>{} <span class="xtr-dump-arrow">⇒</span> {}</li>').format(
                dump(key, depth + 1), dump(value, depth + 1)
            )
            for key, value in pairs
        ]
    elif kind == "object":
        attributes = cast("Sequence[Sequence[object]]", tree.get("attributes", ()))
        rows = [
            Markup('<li><span class="xtr-dump-key">{}</span>: {}</li>').format(
                name, dump(value, depth + 1)
            )
            for name, value in attributes
        ]
    else:
        items = cast("Sequence[object]", tree.get("items", ()))
        rows = [Markup("<li>{}</li>").format(dump(item, depth + 1)) for item in items]
    truncated = tree.get("truncated", 0)
    if isinstance(truncated, int) and truncated > 0:
        rows.append(Markup('<li class="xtr-dump-more">… {} more</li>').format(truncated))
    opened = Markup(" open") if depth < _OPEN_LEVELS else Markup("")
    return Markup(
        '<details class="xtr-dump"{}><summary><span class="xtr-dump-type">{}</span> '
        '<span class="xtr-dump-count">({})</span></summary><ul>{}</ul></details>'
    ).format(opened, type_name, len(rows), Markup("").join(rows))


def _scalar(value: object, type_name: str = "") -> Markup:
    if value is None:
        return Markup('<span class="xtr-dump-null">None</span>')
    if isinstance(value, bool):
        return Markup('<span class="xtr-dump-bool">{}</span>').format(value)
    if isinstance(value, int | float):
        return Markup('<span class="xtr-dump-number">{}</span>').format(value)
    return Markup('<span class="xtr-dump-scalar" title="{}">{}</span>').format(
        type_name, escape(str(value))
    )


def _more(tree: Mapping[str, object]) -> Markup:
    truncated = tree.get("truncated", 0)
    if isinstance(truncated, int) and truncated > 0:
        return Markup(' <span class="xtr-dump-more">… {} more</span>').format(truncated)
    return Markup("")
