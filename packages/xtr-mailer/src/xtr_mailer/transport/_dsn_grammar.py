"""Reading the groups a mailer DSN string puts its DSNs in: ``failover(a roundrobin(b c))``.

A DSN string is one DSN, or a keyword group of members separated by spaces — a member being a
DSN or a group — optionally followed by ``?retry_period=<seconds>``::

    roundrobin(smtp://a failover(smtp://b smtp://c)?retry_period=15)

The string is read in one pass with an explicit stack, never by recursion, and each character
is looked at a bounded number of times, so a hostile string of any length is refused in time
proportional to its length. Groups nest at most :data:`MAX_DEPTH` deep.

Nothing here quotes the string in an error, since a DSN carries credentials: a refusal shows,
cut short, only a keyword it does not know or a retry period it cannot read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from re import Pattern

__all__ = ["GARBAGE", "MAX_DEPTH", "DsnGroup", "DsnNode", "read_dsn_groups"]

Keyword: TypeAlias = Literal["failover", "roundrobin"]

#: How deep groups may nest: far beyond any real configuration, and shallow enough that
#: building, naming and sending through the transports never nears the recursion limit.
MAX_DEPTH: Final = 32

_KEYWORDS: Final[tuple[Keyword, ...]] = ("failover", "roundrobin")
_WORD_THEN_PARENTHESIS: Pattern[str] = re.compile(r"([A-Za-z0-9_]+)\(")
_TOKEN: Pattern[str] = re.compile(r"[^ )]*")
_SPACES: Pattern[str] = re.compile(r" *")
_SECONDS: Pattern[str] = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_RETRY_PERIOD: Final = "retry_period"

_NO_SCHEME: Final = "The mailer DSN must contain a scheme."
#: What is said of anything following a DSN or a group that is no part of it.
GARBAGE: Final = "The mailer DSN has some garbage at the end."


@final
@dataclass(slots=True)
class DsnGroup:
    """A keyword group: its members in order, and the retry period it was given, if any."""

    keyword: Keyword
    members: list[DsnNode] = field(default_factory=list["DsnNode"])
    retry_period: float | None = None


#: A member of a DSN string: one DSN, still unread, or a group.
DsnNode: TypeAlias = "str | DsnGroup"


def read_dsn_groups(text: str) -> tuple[DsnNode, bool]:
    """Read ``text`` into the DSN it starts with, or the group it puts its DSNs in.

    Returns the DSN or the group, and whether it is all of ``text``. Whatever follows it is
    left to the caller to refuse with :data:`GARBAGE` — once it has built what it read, so a
    DSN that cannot be read is reported before the garbage after it.

    Raises:
        InvalidArgumentError: A group is not closed, or has an empty member (``The mailer DSN
            must contain a scheme.``, as an empty DSN has none); a keyword is not known; groups
            nest deeper than :data:`MAX_DEPTH`; a retry period is not a number of seconds; or
            something follows a member of a group that is no part of it.
    """
    text = text.strip()
    closed = _closed_parentheses(text) if "(" in text else frozenset[int]()
    stack: list[DsnGroup] = []
    position = 0
    while True:
        if stack:
            position = _end_of(_SPACES, text, position)
        if stack and text.startswith(")", position):
            node, position = _close(stack.pop(), text, position)
        elif (keyword := _keyword_at(text, position)) is not None:
            if position + len(keyword) not in closed:
                raise InvalidArgumentError(_NO_SCHEME)
            position = _open(stack, keyword, position)
            continue
        else:
            node, position = _token(text, position)
        while True:
            if not stack:
                return node, position == len(text)
            stack[-1].members.append(node)
            if text.startswith(" ", position):
                break
            if not text.startswith(")", position):
                # A group is followed by something that is neither a space nor its parent's end.
                raise InvalidArgumentError(GARBAGE)
            node, position = _close(stack.pop(), text, position)


def _keyword_at(text: str, position: int) -> Keyword | None:
    """Return the keyword whose group opens at ``position``, or ``None``."""
    for keyword in _KEYWORDS:
        if text.startswith(f"{keyword}(", position):
            return keyword
    return None


def _open(stack: list[DsnGroup], keyword: Keyword, position: int) -> int:
    """Open a ``keyword`` group at ``position`` and return where its first member starts.

    Raises:
        InvalidArgumentError: The group nests too deep.
    """
    if len(stack) == MAX_DEPTH:
        raise InvalidArgumentError(
            f"The mailer DSN nests its transports more than {MAX_DEPTH} deep."
        )
    stack.append(DsnGroup(keyword))
    return position + len(keyword) + 1


def _token(text: str, position: int) -> tuple[str, int]:
    """Read the DSN at ``position``, up to a space or a closing parenthesis.

    Raises:
        InvalidArgumentError: It starts like a group of an unknown keyword, or it is empty.
    """
    word = _WORD_THEN_PARENTHESIS.match(text, position)
    if word is not None:
        listed = '", "'.join(_KEYWORDS)
        raise InvalidArgumentError(
            f'The "{shown(word.group(1))}" keyword is not valid (valid ones are "{listed}").'
        )
    end = _end_of(_TOKEN, text, position)
    if end == position:
        raise InvalidArgumentError(_NO_SCHEME)
    return text[position:end], end


def _close(group: DsnGroup, text: str, position: int) -> tuple[DsnGroup, int]:
    """Close ``group`` at the parenthesis at ``position``, reading the retry period after it.

    Raises:
        InvalidArgumentError: The group is empty, or its retry period is not seconds.
    """
    if not group.members:
        raise InvalidArgumentError(_NO_SCHEME)
    position += 1
    if not text.startswith("?", position):
        return group, position
    end = _end_of(_TOKEN, text, position + 1)
    key, separator, value = text[position + 1 : end].partition("=")
    if key != _RETRY_PERIOD or not separator or "&" in value:
        # Not an option of the group: whatever it is, it is no part of the DSN string.
        raise InvalidArgumentError(GARBAGE)
    if _SECONDS.fullmatch(value) is None:
        raise InvalidArgumentError(
            f'The "{_RETRY_PERIOD}" option must be a number of seconds, zero or more; '
            f'"{shown(value)}" is not.'
        )
    group.retry_period = float(value)
    return group, end


def _end_of(pattern: Pattern[str], text: str, position: int) -> int:
    """Return where ``pattern``, which matches the empty string too, stops matching."""
    match = pattern.match(text, position)
    return position if match is None else match.end()


def _closed_parentheses(text: str) -> frozenset[int]:
    """Return the position of every opening parenthesis a later one closes, in one pass."""
    opened: list[int] = []
    closed: set[int] = set()
    for position, character in enumerate(text):
        if character == "(":
            opened.append(position)
        elif character == ")" and opened:
            closed.add(opened.pop())
    return frozenset(closed)
