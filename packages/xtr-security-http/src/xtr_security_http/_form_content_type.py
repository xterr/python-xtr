"""Telling a submitted form by the media type its body is encoded in.

Every step that reads a body for the form it may carry asks it first: the
chain's authentication step, which reads a submitted form before handing the
request on; the readers of a posted parameter; the form login, which may refuse
a submission that is not one; the extractor of a bearer token posted in a form.
They all read the ``Content-Type`` by the one rule here, so a request one of
them takes for a form the others do too.
"""

from __future__ import annotations

from typing import Final

__all__ = ["is_form_content_type"]

#: The media types a submitted form is encoded in.
_FORM_MEDIA_TYPES: Final = frozenset({"application/x-www-form-urlencoded", "multipart/form-data"})


def is_form_content_type(
    content_type: str,
    *,
    media_types: frozenset[str] = _FORM_MEDIA_TYPES,
) -> bool:
    """Tell whether a ``Content-Type`` header names one of the form encodings.

    The media type is weighed whole — its parameters dropped, its case
    ignored — and must be one of the encodings exactly: the rule by which the
    kernel decides that a body parses into a form, so a request told for a
    form here is one whose parsed body holds the form's fields. A type that
    only starts like one, ``application/x-www-form-urlencodedX``, is no form.

    Args:
        content_type: The value of the ``Content-Type`` header.
        media_types: The form encodings that count — both by default. A
            reader that parses only one of them narrows the set to it, and
            the media type is weighed against it by the same rule.
    """
    return content_type.partition(";")[0].strip().lower() in media_types
