"""Parameterized headers — Content-Type, Content-Disposition — and their RFC 2231 writer."""

from __future__ import annotations

import re
import urllib.parse
from email.utils import quote
from typing import TYPE_CHECKING, Final

from xtr_mime._error_text import capped
from xtr_mime.exception import RfcComplianceError

from ._grammar import FOLD_WIDTH, SOURCE_FOLD, TOKEN, body_of, check_token, refuse_forbidden
from ._policy import CONTENT_TYPE, PARAMETERIZED, FoldedHeader, parameters_of

if TYPE_CHECKING:
    from email.headerregistry import BaseHeader

    from ._values import Parameterized

__all__ = ["parameterized_header"]

# RFC 2231, 7: a token without "*", "'" and "%", which carry the parameter's own encoding.
_PARAMETER_NAME: Final = re.compile(r"[!#$&+\-.^_`{|}~0-9A-Za-z]+")


def parameterized_header(name: str, value: Parameterized) -> BaseHeader | FoldedHeader:
    _check_parameterized(name, value)
    registry = CONTENT_TYPE if name.lower() == "content-type" else PARAMETERIZED
    header = registry(name, _join_parameters(value))
    # The engine decodes an encoded word in a quoted parameter, which may hold what the value
    # itself did not.
    for key, item in parameters_of(header).items():
        refuse_forbidden(f"The decoded {key} parameter", str(item))
    if not any("=?" in item for item in value.parameters.values()):
        return header
    # The engine wrote the decoded text, which a reader would take for the name: a filename
    # filter would check another name than the one given. The field is written by hand.
    folded = _write_parameters(name, value)
    read = parameters_of(registry(name, SOURCE_FOLD.sub("", body_of(name, folded))))
    if list(read.items()) != [(key.lower(), item) for key, item in value.parameters.items()]:
        raise RfcComplianceError(
            f"The {name} header would not read back to the parameters it was given."
        )
    return FoldedHeader(name, SOURCE_FOLD.sub("", body_of(name, folded)).strip(), folded)


def _write_parameters(name: str, value: Parameterized) -> str:
    """Write a parameterized field one of whose parameters holds ``=?``.

    Such a parameter, and any that is not ASCII, is written in RFC 2231 form, percent-encoded
    in UTF-8 — split into numbered sections when too long for a line — so it holds no ``=?``
    any reader takes for an encoded word; the others are quoted. The field folds between
    parameters.
    """
    pieces: list[str] = []
    for key, item in value.parameters.items():
        if "=?" in item or not item.isascii():
            pieces += _percent_encoded(key, item)
        else:
            pieces.append(f'{key}="{quote(item)}"')
    lines = [f"{name}: {value.value}"]
    for piece in pieces:
        if len(lines[-1]) + len(piece) + 2 > FOLD_WIDTH:
            lines[-1] += ";"
            lines.append(f" {piece}")
        else:
            lines[-1] += f"; {piece}"
    return "\r\n".join(lines) + "\r\n"


def _percent_encoded(key: str, item: str) -> list[str]:
    encoded = urllib.parse.quote(item, safe="")
    whole = f"{key}*=utf-8''{encoded}"
    if len(whole) + 2 <= FOLD_WIDTH:
        return [whole]
    sections: list[str] = []
    start = 0
    while start < len(encoded):
        head = f"{key}*{len(sections)}*=" + ("" if sections else "utf-8''")
        end = min(len(encoded), start + FOLD_WIDTH - 2 - len(head))
        # A section never splits a percent-encoded octet.
        end -= next((i for i in (1, 2) if encoded[end - i] == "%" and end < len(encoded)), 0)
        sections.append(head + encoded[start:end])
        start = end
    return sections


def _check_parameterized(name: str, value: Parameterized) -> None:
    if name.lower() == "content-type":
        maintype, slash, subtype = value.value.partition("/")
        if not (slash and TOKEN.fullmatch(maintype) and TOKEN.fullmatch(subtype)):
            raise RfcComplianceError(f'"{capped(value.value)}" is not a media type: type/subtype.')
    else:
        check_token(f"{name} value", value.value)
    for key, item in value.parameters.items():
        if not _PARAMETER_NAME.fullmatch(key):
            raise RfcComplianceError(f'"{capped(key)}" is not a parameter name: an RFC 2231 token.')
        refuse_forbidden(f"The {key} parameter", item)


def _join_parameters(value: Parameterized) -> str:
    parameters = (f'{key}="{quote(item)}"' for key, item in value.parameters.items())
    return "; ".join((value.value, *parameters))
