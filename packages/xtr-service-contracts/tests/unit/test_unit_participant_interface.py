from __future__ import annotations

from xtr_service_contracts import UnitParticipantInterface


class Participant:
    def unit_began(self) -> object | None:
        return "token"

    def unit_ended(self, token: object | None) -> None:
        del token


class OnlyBegins:
    def unit_began(self) -> object | None:
        return None


def test_a_class_with_both_hooks_is_a_unit_participant() -> None:
    assert isinstance(Participant(), UnitParticipantInterface)


def test_a_class_missing_a_hook_is_not() -> None:
    assert not isinstance(OnlyBegins(), UnitParticipantInterface)
