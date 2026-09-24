from __future__ import annotations

import logging

from xtr_logging.bridge.stdlib.level_mapping import from_stdlib, register_level_names, to_stdlib
from xtr_logging.level import Level


def test_to_stdlib_gives_each_level_its_standard_number() -> None:
    numbers = {level: to_stdlib(level) for level in Level}

    assert numbers == {
        Level.DEBUG: 10,
        Level.INFO: 20,
        Level.NOTICE: 25,
        Level.WARNING: 30,
        Level.ERROR: 40,
        Level.CRITICAL: 50,
        Level.ALERT: 55,
        Level.EMERGENCY: 60,
    }


def test_from_stdlib_maps_the_five_standard_numbers_to_their_levels() -> None:
    assert from_stdlib(logging.DEBUG) is Level.DEBUG
    assert from_stdlib(logging.INFO) is Level.INFO
    assert from_stdlib(logging.WARNING) is Level.WARNING
    assert from_stdlib(logging.ERROR) is Level.ERROR
    assert from_stdlib(logging.CRITICAL) is Level.CRITICAL


def test_from_stdlib_maps_the_three_extra_numbers_to_their_levels() -> None:
    assert from_stdlib(25) is Level.NOTICE
    assert from_stdlib(55) is Level.ALERT
    assert from_stdlib(60) is Level.EMERGENCY


def test_from_stdlib_rounds_a_number_between_levels_down_to_the_less_severe() -> None:
    assert from_stdlib(logging.WARNING + 1) is Level.WARNING
    assert from_stdlib(24) is Level.INFO
    assert from_stdlib(26) is Level.NOTICE
    assert from_stdlib(45) is Level.ERROR


def test_from_stdlib_treats_anything_below_info_as_debug() -> None:
    assert from_stdlib(logging.NOTSET) is Level.DEBUG
    assert from_stdlib(19) is Level.DEBUG


def test_from_stdlib_treats_anything_at_or_above_emergency_as_emergency() -> None:
    assert from_stdlib(60) is Level.EMERGENCY
    assert from_stdlib(1000) is Level.EMERGENCY


def test_register_level_names_names_the_three_extra_levels() -> None:
    register_level_names()

    assert logging.getLevelName(25) == "NOTICE"
    assert logging.getLevelName(55) == "ALERT"
    assert logging.getLevelName(60) == "EMERGENCY"


def test_register_level_names_settles_on_the_same_names_when_called_again() -> None:
    register_level_names()
    register_level_names()

    assert logging.getLevelName(25) == "NOTICE"
