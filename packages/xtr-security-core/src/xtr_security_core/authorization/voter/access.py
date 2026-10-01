"""The three answers a voter can give."""

from __future__ import annotations

from enum import IntEnum

__all__ = ["Access"]


class Access(IntEnum):
    """A voter's answer to one access question.

    Ordered on purpose: ``GRANTED`` above ``ABSTAIN`` above ``DENIED``, so a
    strategy can compare and count answers as integers. A voter that has no
    opinion abstains rather than denying — abstaining leaves the decision to
    the others, while denying weighs against access.
    """

    GRANTED = 1
    ABSTAIN = 0
    DENIED = -1
