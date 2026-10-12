from __future__ import annotations

import dataclasses

from xtr_remote_event.bundle import RemoteEventConfig


def test_it_is_buildable_with_no_arguments_and_has_nothing_to_set() -> None:
    assert dataclasses.fields(RemoteEventConfig()) == ()


def test_two_of_them_are_one_value() -> None:
    assert RemoteEventConfig() == RemoteEventConfig()
