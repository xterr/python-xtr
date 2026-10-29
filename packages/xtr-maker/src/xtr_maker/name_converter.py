"""NameConverter: one name, written as a class, a module, a command or a table."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["NameConverter"]

_SEPARATOR: Final = re.compile(r"[^A-Za-z0-9]+")
"""What splits a name into chunks before each chunk is split at its case changes."""

_WORD: Final = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+[0-9]*|[A-Z]+[0-9]*|[0-9]+")
"""One word of a chunk: an acronym before a capitalised word, a word, an acronym, a number."""

_LAST_WORD: Final = re.compile(r"([A-Z]?[a-z]+|[A-Z]+)$")
"""The word a name ends with, the only one a plural changes."""

_UNCOUNTABLE: Final = frozenset(
    {
        "data",
        "equipment",
        "feedback",
        "fish",
        "information",
        "metadata",
        "money",
        "news",
        "series",
        "sheep",
        "software",
        "species",
    }
)
"""Words that are the same in the singular and the plural."""

_IRREGULAR: Final = {
    "analysis": "analyses",
    "cache": "caches",
    "child": "children",
    "cookie": "cookies",
    "criterion": "criteria",
    "foot": "feet",
    "goose": "geese",
    "half": "halves",
    "index": "indices",
    "knife": "knives",
    "leaf": "leaves",
    "life": "lives",
    "man": "men",
    "matrix": "matrices",
    "mouse": "mice",
    "movie": "movies",
    "ox": "oxen",
    "person": "people",
    "quiz": "quizzes",
    "shelf": "shelves",
    "tooth": "teeth",
    "vertex": "vertices",
    "wife": "wives",
    "wolf": "wolves",
    "woman": "women",
}
"""Singulars whose plural no rule below makes, or whose plural the rules would read back wrong."""

_SINGULAR_OF: Final = {plural: singular for singular, plural in _IRREGULAR.items()}

_PLURAL_RULES: Final = (
    (re.compile(r"is$"), "es"),
    (re.compile(r"(?<=[^aeiou])y$"), "ies"),
    (re.compile(r"(s|x|z|ch|sh)$"), r"\1es"),
)
_SINGULAR_RULES: Final = (
    (re.compile(r"ies$"), "y"),
    (re.compile(r"yses$"), "ysis"),
    (re.compile(r"(?<=[^aeiou]u)ses$"), "s"),
    (re.compile(r"(x|ch|sh|ss)es$"), r"\1"),
)
_SINGULAR_ENDINGS: Final = ("ss", "us", "is")
"""Endings of a word ending in ``s`` that is already singular: ``class``, ``status``, ``axis``."""


@final
class NameConverter:
    """Turns one name into the forms the generated code spells it in.

    A person types ``place order``, ``PlaceOrder`` or ``place_order``; the
    class is ``PlaceOrder``, its module ``place_order``, a console command
    ``place-order`` and a table ``place_orders``. Every form is made from the
    same words, so the forms of one name always agree.

    The plural covers English as names in code use it: a few rules and a list
    of irregular words, applied to the last word only — ``order_item`` becomes
    ``order_items``. It is not a dictionary, and a name it gets wrong is
    changed where it is written.
    """

    __slots__ = ()

    @staticmethod
    def words(value: str) -> tuple[str, ...]:
        """Split ``value`` into its words, at separators and at case changes."""
        return tuple(
            word.group() for chunk in _SEPARATOR.split(value) for word in _WORD.finditer(chunk)
        )

    @staticmethod
    def as_class_name(value: str) -> str:
        """Return ``value`` as a class name: ``place order`` → ``PlaceOrder``.

        A name already written as one — an identifier starting with a capital,
        with no underscore — is kept as typed, so ``HTTPClient`` stays
        ``HTTPClient`` rather than becoming ``HttpClient``.
        """
        if value.isidentifier() and value[0].isupper() and "_" not in value:
            return value
        return "".join(word[0].upper() + word[1:] for word in NameConverter.words(value))

    @staticmethod
    def as_snake_case(value: str) -> str:
        """Return ``value`` as a module or function name: ``PlaceOrder`` → ``place_order``."""
        return "_".join(word.lower() for word in NameConverter.words(value))

    @staticmethod
    def as_kebab_case(value: str) -> str:
        """Return ``value`` as a console name: ``PlaceOrder`` → ``place-order``."""
        return "-".join(word.lower() for word in NameConverter.words(value))

    @staticmethod
    def as_table_name(value: str) -> str:
        """Return ``value`` as a plural, snake-cased table name: ``OrderItem`` → ``order_items``."""
        return NameConverter.pluralize(NameConverter.as_snake_case(value))

    @staticmethod
    def pluralize(value: str) -> str:
        """Return ``value`` with its last word in the plural, keeping its case."""
        return _replace_last_word(value, _plural)

    @staticmethod
    def singularize(value: str) -> str:
        """Return ``value`` with its last word in the singular, keeping its case."""
        return _replace_last_word(value, _singular)


def _replace_last_word(value: str, change: Callable[[str], str]) -> str:
    """Return ``value`` with its last word changed by ``change``, cased as it was."""
    found = _LAST_WORD.search(value)
    if found is None:
        return value
    word = found.group(1)
    changed = change(word.lower())
    if len(word) > 1 and word.isupper():
        changed = changed.upper()
    elif word[0].isupper():
        changed = changed[0].upper() + changed[1:]
    return value[: found.start(1)] + changed


def _plural(word: str) -> str:
    """Return the plural of a lowercase ``word``."""
    if word in _UNCOUNTABLE or word in _SINGULAR_OF:
        return word
    irregular = _IRREGULAR.get(word)
    if irregular is not None:
        return irregular
    for pattern, replacement in _PLURAL_RULES:
        if pattern.search(word):
            return pattern.sub(replacement, word)
    return f"{word}s"


def _singular(word: str) -> str:
    """Return the singular of a lowercase ``word``."""
    if word in _UNCOUNTABLE or word in _IRREGULAR:
        return word
    irregular = _SINGULAR_OF.get(word)
    if irregular is not None:
        return irregular
    for pattern, replacement in _SINGULAR_RULES:
        if pattern.search(word):
            return pattern.sub(replacement, word)
    if word.endswith("s") and not word.endswith(_SINGULAR_ENDINGS):
        return word[:-1]
    return word
