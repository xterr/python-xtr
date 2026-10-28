"""What the application's workflows move, each keeping its marking in ``marking``."""

from __future__ import annotations


class Article:
    marking: object = None


class PullRequest:
    marking: object = None


class Ticket:
    """Moved by two workflows: one picks it by class, the other through a support strategy."""

    marking: object = None
