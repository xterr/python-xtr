"""One voter's answer, with the reasons behind it."""

from __future__ import annotations

from dataclasses import dataclass, field

from .access import Access

__all__ = ["Vote"]


@dataclass(slots=True)
class Vote:
    """What one voter answered, and why.

    A decision collects a vote per voter that had an opinion, so a refusal can
    be explained rather than merely returned. A voter fills in its reasons as
    it decides; the manager records the answer it returned.

    Attributes:
        voter: The voter that cast this, once the manager records it. Held
            loosely — the record does not depend on the voter's contract.
        result: The answer the voter gave.
        reasons: Human-readable reasons the voter added.
        extra_data: Anything else the voter wants a reader of the decision to see.
    """

    voter: object | None = None
    result: Access = Access.ABSTAIN
    reasons: list[str] = field(default_factory=list)
    extra_data: dict[str, object] = field(default_factory=dict)
    _re_authentication_attribute: str | None = field(default=None, init=False, repr=False)

    def add_reason(self, reason: str) -> None:
        """Add a human-readable reason for this vote."""
        self.reasons.append(reason)

    @property
    def re_authentication_attribute(self) -> str | None:
        """The denied attribute a fresh authentication could grant, if one was requested."""
        return self._re_authentication_attribute

    def request_re_authentication(self, attribute: str) -> None:
        """Tell the firewall a fresh authentication could grant the attribute this vote denies.

        Also used for an attribute a closure this vote ran was denied. The
        firewall then starts a re-authentication rather than answering with a
        refusal. With a strategy other than the affirmative one, another voter
        denying the same attribute can leave the user denied after
        re-authenticating.
        """
        self._re_authentication_attribute = attribute
