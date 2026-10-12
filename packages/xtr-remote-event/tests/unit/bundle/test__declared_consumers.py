from __future__ import annotations

import pytest

from xtr_remote_event.bundle._declared_consumers import DeclaredConsumers
from xtr_remote_event.exception import LogicError


class First:
    pass


class Second:
    pass


def test_it_records_the_class_answering_for_each_name() -> None:
    declared = DeclaredConsumers()

    _ = declared.add("stripe", First)
    _ = declared.add("mailgun", Second)

    assert dict(declared.items()) == {"stripe": First, "mailgun": Second}


def test_a_class_is_new_only_the_first_time_it_is_recorded() -> None:
    declared = DeclaredConsumers()

    assert declared.add("stripe", First) is True
    assert declared.add("checkout", First) is False
    assert declared.add("mailgun", Second) is True


def test_recording_a_class_again_under_a_name_it_already_has_changes_nothing() -> None:
    declared = DeclaredConsumers()

    _ = declared.add("stripe", First)
    assert declared.add("stripe", First) is False

    assert dict(declared.items()) == {"stripe": First}


def test_two_classes_cannot_answer_for_one_name() -> None:
    declared = DeclaredConsumers()
    _ = declared.add("stripe", First)

    with pytest.raises(LogicError) as caught:
        _ = declared.add("stripe", Second)

    assert str(caught.value) == (
        'The remote event consumer name "stripe" is declared by both First and Second.'
    )
