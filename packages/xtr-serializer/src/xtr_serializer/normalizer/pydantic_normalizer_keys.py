"""The context keys the pydantic normalizer reads.

Kept apart from the normalizer, so the context builder that sets them can be imported without
it. Each constant's value is the key as a context carries it: a context written by hand uses the
same strings.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "ALLOW_EXTRA_ATTRIBUTES",
    "ATTRIBUTES",
    "BY_ALIAS",
    "FROM_ATTRIBUTES",
    "IGNORED_ATTRIBUTES",
    "POPULATE_BY_NAME",
    "SKIP_DEFAULT_VALUES",
    "SKIP_NULL_VALUES",
    "SKIP_UNSET_VALUES",
    "STRICT",
]

ATTRIBUTES: Final = "attributes"
"""The names of the fields to write, as a set; every other field is left out.

Lets one model serve answers that show only part of it. Every field is written when absent.
"""

IGNORED_ATTRIBUTES: Final = "ignored_attributes"
"""The names of fields never to write, as a set.

For a field that must stay out of one answer — a password hash, an internal note — without a
second model to leave it out of. No field is left out when absent.
"""

SKIP_NULL_VALUES: Final = "skip_null_values"
"""Whether a field holding ``None`` is left out of what is written.

Off when absent, so a reader can tell a field that is empty from one that is missing.
"""

SKIP_UNSET_VALUES: Final = "skip_unset_values"
"""Whether a field given no value when its object was built is left out of what is written.

What is written is then what the sender said, not the defaults filled in for what it did not —
the shape a partial update needs. Off when absent.
"""

SKIP_DEFAULT_VALUES: Final = "skip_default_values"
"""Whether a field holding its default value is left out of what is written.

Keeps the text short when most fields keep their defaults, at the cost of a reader that must
know them. Off when absent.
"""

BY_ALIAS: Final = "by_alias"
"""Whether fields are written and read under their alias rather than their name.

On when absent: an alias is declared because the data outside spells the field that way, so
writing under it and reading it back agree with that data.
"""

STRICT: Final = "strict"
"""Whether reading refuses data that only converts to the declared type, such as ``"1"`` for an
``int``, instead of converting it.

For data from a sender that ought to know the types. When absent, the type's own pydantic
configuration decides.
"""

ALLOW_EXTRA_ATTRIBUTES: Final = "allow_extra_attributes"
"""Whether data may carry fields its type does not declare.

Allowed, they are dropped; refused, reading fails with
:class:`~xtr_serializer.exception.ExtraAttributesError` naming them — so a client hears about a
misspelled field instead of having it ignored. When absent, the type's own pydantic
configuration decides.
"""

FROM_ATTRIBUTES: Final = "from_attributes"
"""Whether reading accepts an object as well as a mapping, taking each field from the object's
attribute of the same name.

For turning one object into another — a database row into the model an answer is written
from. Off when absent: the data is read as JSON.
"""

POPULATE_BY_NAME: Final = "populate_by_name"
"""Whether reading accepts a field under its own name as well as under its alias.

For data written both by a sender that uses the aliases and by code that uses the names. When
absent, the type's own pydantic configuration decides.
"""
