"""Puts an email's text, HTML and attachments together into one body part.

The tree is ``mixed > related > alternative(text, html)``, each level only when needed: an
attachment the HTML refers to by ``cid:`` goes into ``related`` next to it and is shown inline,
every other attachment into ``mixed`` after the body.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, BinaryIO, Final, Protocol

from ._error_text import body_charset_error
from ._html_references import referenced_names
from .exception import InvalidArgumentError, LogicError
from .part import AlternativePart, MixedPart, RelatedPart, TextPart

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .part import AbstractPart, DataPart

__all__ = ["NO_BODY", "assemble_body"]

NO_BODY: Final = "A message must have a text or an HTML part or attachments."


class _Content(Protocol):
    """What a body is put together from: an email's text, HTML and attachments."""

    def get_text_body(self) -> str | bytes | BinaryIO | None: ...

    def get_text_charset(self) -> str | None: ...

    def get_html_body(self) -> str | bytes | BinaryIO | None: ...

    def get_html_charset(self) -> str | None: ...

    def get_attachments(self) -> list[DataPart]: ...


def assemble_body(email: _Content) -> AbstractPart:
    """Build the body of ``email`` from its text, HTML and attachments.

    An attachment the HTML refers to is shown inline, named after its content id when it has
    no name, and the HTML is rewritten to refer to it by that id. Two attachments the HTML
    refers to by one name are one too many: the second is left out of the body.

    Raises:
        LogicError: The email has no text, no HTML and no attachment.
        InvalidArgumentError: The HTML body is bytes in a charset Python does not know, or
            that cannot read them, or write them back once their references are rewritten.
    """
    html, related, others = _prepare_parts(email)
    text = email.get_text_body()
    part: AbstractPart | None = None if text is None else TextPart(text, email.get_text_charset())
    if html is not None:
        part = html if part is None else AlternativePart(part, html)
        if related:
            part = RelatedPart(part, *related)
    if others:
        part = MixedPart(*others) if part is None else MixedPart(part, *others)
    if part is None:
        raise LogicError(NO_BODY)
    return part


def _prepare_parts(email: _Content) -> tuple[TextPart | None, list[DataPart], list[DataPart]]:
    """Return the HTML part, the attachments it refers to, and the other attachments."""
    attachments = email.get_attachments()
    html = email.get_html_body()
    if html is None:
        return None, [], list(attachments)
    charset = email.get_html_charset() or "utf-8"
    content = TextPart(html, charset, "html").get_body()
    names: Sequence[str] = referenced_names(_as_text(content, charset)) if attachments else ()
    related: dict[str, DataPart] = {}
    replacements: dict[str, str] = {}
    others: list[DataPart] = []
    for part in attachments:
        name = next((name for name in names if _is_named(part, name)), None)
        if name is None:
            others.append(part)
        elif name not in related:
            replacements[f"cid:{name}"] = f"cid:{part.get_content_id()}"
            related[name] = part
            own_name = part.get_name()
            _ = part.set_name(part.get_content_id() if own_name is None else own_name).as_inline()
    if replacements:
        rewritten = _replace_all(_as_text(content, charset), replacements)
        content = rewritten if isinstance(content, str) else _as_bytes(rewritten, charset)
    return TextPart(content, charset, "html"), list(related.values()), others


def _as_text(content: str | bytes, charset: str) -> str:
    if isinstance(content, str):
        return content
    try:
        return content.decode(charset, "surrogateescape")
    except LookupError as error:
        raise InvalidArgumentError(f"The charset {charset!r} is unknown.") from error
    except ValueError as error:
        # The codec refuses the bytes, or a null byte in the charset names no codec.
        raise body_charset_error(charset, error) from error


def _as_bytes(html: str, charset: str) -> bytes:
    """Write ``html`` back in the charset it was read in; the charset is known by now."""
    try:
        return html.encode(charset, "surrogateescape")
    except UnicodeError as error:
        raise body_charset_error(charset, error) from error


def _is_named(part: DataPart, name: str) -> bool:
    return name == part.get_name() or (part.has_content_id() and name == part.get_content_id())


def _replace_all(html: str, replacements: Mapping[str, str]) -> str:
    """Replace every reference at once, the longest first, never inside a replacement made.

    One after the other, ``cid:logo`` would be rewritten inside ``cid:logo_2`` too.
    """
    keys = sorted(replacements, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(key) for key in keys))
    return pattern.sub(lambda match: replacements[match.group()], html)
