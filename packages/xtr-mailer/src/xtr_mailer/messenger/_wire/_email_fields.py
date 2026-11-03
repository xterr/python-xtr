"""What an email builds its body from, and the template of one a provider renders, on the queue.

The text and the HTML travel as they were given, a stream drained into bytes; the attachments
as their parts; a template as its reference and its variables, which must be JSON already.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from xtr_mime import DataPart, TextPart

from xtr_mailer.remote_template_email import RemoteTemplateEmail

from ._json import (
    JsonObject,
    content,
    fields,
    items,
    optional_text,
    refuse,
    text,
    written_content,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mime import AbstractPart, Email
    from xtr_mime.email import Body

__all__ = ["EMAIL_FIELDS", "TEMPLATE_FIELD", "read_email_fields", "write_email_fields"]

EMAIL_FIELDS: Final = ("text", "text_charset", "html", "html_charset", "attachments")
TEMPLATE_FIELD: Final = "template"

_SHORT: Final = 64


def write_email_fields(
    email: Email, write_part: Callable[[AbstractPart], JsonObject]
) -> JsonObject:
    """Write the text, HTML and attachments of ``email``, and the template it is rendered from.

    Raises:
        InvalidArgumentError: As ``write_part`` does for an attachment.
    """
    written: JsonObject = {
        "text": _written_body(email.get_text_body()),
        "text_charset": email.get_text_charset(),
        "html": _written_body(email.get_html_body()),
        "html_charset": email.get_html_charset(),
        "attachments": [write_part(part) for part in email.get_attachments()],
    }
    if isinstance(email, RemoteTemplateEmail):
        template = email.get_remote_template()
        written[TEMPLATE_FIELD] = (
            None
            if template is None
            else {"reference": template.get_reference(), "variables": template.get_variables()}
        )
    return written


def read_email_fields(
    email: Email,
    found: JsonObject,
    path: str,
    read_part: Callable[[object, str], AbstractPart],
) -> None:
    """Give ``email`` the fields :func:`write_email_fields` wrote.

    Raises:
        InvalidArgumentError: A field is not what it must be.
    """
    for name in ("text", "html"):
        body = None if found[name] is None else content(found[name], f"{path}.{name}")
        charset = optional_text(found[f"{name}_charset"], f"{path}.{name}_charset", _SHORT)
        if body is None and charset is None:
            continue
        if charset is None:
            refuse(f"{path}.{name}_charset", "is null where a body is set")
        _ = email.text(body, charset) if name == "text" else email.html(body, charset)
    for index, item in enumerate(items(found["attachments"], f"{path}.attachments")):
        where = f"{path}.attachments[{index}]"
        part = read_part(item, where)
        if not isinstance(part, DataPart):
            refuse(where, "is not an attachment")
        _ = email.add_part(part)
    if isinstance(email, RemoteTemplateEmail) and found[TEMPLATE_FIELD] is not None:
        where = f"{path}.{TEMPLATE_FIELD}"
        template = fields(found[TEMPLATE_FIELD], where, ("reference", "variables"))
        reference = text(template["reference"], f"{where}.reference")
        variables = template["variables"]
        if type(variables) is not dict:
            refuse(f"{where}.variables", "is not an object")
        _ = email.template(reference, cast("JsonObject", variables))


def _written_body(body: Body | None) -> JsonObject | None:
    """Write a body as it was given; a stream is read now, from its start when it can seek."""
    return None if body is None else written_content(TextPart(body).get_body())
