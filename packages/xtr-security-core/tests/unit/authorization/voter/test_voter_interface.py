"""The voter interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authorization.voter import ClosureVoter, RoleVoter, VoterInterface


def test_a_voter_satisfies_the_interface() -> None:
    assert isinstance(RoleVoter(), VoterInterface)
    assert isinstance(ClosureVoter(), VoterInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), VoterInterface)
