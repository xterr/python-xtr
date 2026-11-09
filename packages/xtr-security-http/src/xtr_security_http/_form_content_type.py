"""Telling a submitted form by the media type its body is encoded in.

Two steps of a login ask it: the chain's authentication step, which reads a
submitted form before handing the request on, and the form login, which may
refuse a submission that is not one. Both read the ``Content-Type`` by the one
rule here, so a request one of them takes for a form the other does too.
"""

from __future__ import annotations

from typing import Final

__all__ = ["is_form_content_type"]

#: The media types a submitted form is encoded in.
_FORM_MEDIA_TYPES: Final = frozenset({"application/x-www-form-urlencoded", "multipart/form-data"})


def is_form_content_type(content_type: str) -> bool:
    """Tell whether a ``Content-Type`` header names one of the form encodings.

    The media type is weighed whole — its parameters dropped, its case
    ignored — and must be one of the two exactly: the rule by which the
    kernel decides that a body parses into a form, so a request told for a
    form here is one whose parsed body holds the form's fields. A type that
    only starts like one, ``application/x-www-form-urlencodedX``, is no form.
    """
    return content_type.partition(";")[0].strip().lower() in _FORM_MEDIA_TYPES
